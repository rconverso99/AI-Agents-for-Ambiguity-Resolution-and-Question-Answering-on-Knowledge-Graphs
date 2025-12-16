import asyncio
from typing import TypedDict, Annotated

from google import genai
import google.api_core.exceptions
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from sentence_transformers import SentenceTransformer

import app.ExtractEntity as ee
import json
import os
from langgraph.graph import StateGraph, START, END, add_messages
from langchain_neo4j import Neo4jGraph
from difflib import SequenceMatcher

import app.TreeByModel as tbm
import re
import app.UpdateGraph as ug


neo4j_graph = None
model = SentenceTransformer('all-MiniLM-L6-v2')
gemini_api_key = ""

sentence = []

def run_pipeline(uri, user, password, api_key, _frase_):
    global neo4j_graph
    neo4j_graph = Neo4jGraph(refresh_schema=False, url=uri, username=user, password=password)
    global gemini_api_key
    gemini_api_key = api_key
    global sentence
    sentence = [_frase_]
    asyncio.run(run_graph())


class InterpretationMessage(BaseMessage):
    type: str = "interpretation"
    content: str
    interpretation_type: str | None = None


class State(TypedDict, total=False):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    user_question: str
    tree: dict[str, list]
    entities: list
    question: bool
    messages: Annotated[list, add_messages]
    ambig_sent: list
    ambig_sent_tot: list


def itera_e_analizza(nodo, entities):
    if nodo['text'] in entities:
        nodo['isEntity'] = "true"
    else:
        nodo['isEntity'] = "false"

    if 'isEntity' in nodo:
        chiavi_ordinate = ['text', 'lemma', 'pos', 'dep', 'isEntity']

        if 'children' in nodo:
            chiavi_ordinate.append('children')

        chiavi_esistenti = list(nodo.keys())

        for chiave in chiavi_esistenti:
            if chiave not in chiavi_ordinate:
                chiavi_ordinate.append(chiave)

        nodo_ordinato = {k: nodo[k] for k in chiavi_ordinate if k in nodo}
        nodo.clear()
        nodo.update(nodo_ordinato)

    if 'children' in nodo and nodo['children']:
        for figlio in nodo['children']:
            itera_e_analizza(figlio, entities)


def init(state: State):
    # text_user = "Anna guarda Francesco mentre attraversa la strada"
    global sentence
    if len(sentence) == 0 or sentence[-1] == "":
        text_user = input("User: ")
    else:
        text_user = sentence[-1]
    fake_ambig = [""]
    triple = {}
    return {"messages": [text_user], "ambig_sent": fake_ambig, "tree": triple, "user_question": text_user}


def updateGraph(state: State):
    # text_user = "Anna guarda Francesco mentre attraversa la strada"
    flag = 0
    triple = state["tree"]
    while flag == 0:  # Serve per risolvere i problemi di rete di gemini
        try:
            sent = state["messages"][-1]
            triple[sent.content] = ug.run_pipeline(neo4j_graph, gemini_api_key, sent)
            flag = 1
        except Exception as e:
            print("Errore catchato: ", e)
            flag = 0
    return {"tree": triple}


def chatbot_init(
        state: State):  # Qui inseriremo la logica dove verifichiamo se è una domanda o un'affermazione da mettere a DB
    client = genai.Client(api_key=gemini_api_key)
    question = state["user_question"]  # state["messages"][-1].content
    system_message = (
        f"""Il tuo compito è riconoscere se un testo rappresenta una domanda oppure no.
            REGOLE:
            Non aggiungere alcun commento, limitati a rispondere y se il testo è una domanda, rispondere n se il testo non è una domanda.
            Esempio:
            Testo: Il cane è un uccello?
            Output: y
            Testo: Gianluca mangia la pasta?
            Output: y
            Testo: Anna è innamorata di Luca
            Output: n
            \n
            Testo: {question}
            Output:
                    """
    )
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[system_message]
    )
    new_text = result.text
    if "y" in new_text:
        return {"question": True}
    else:
        return {"question": False}


def chatbot_ambiguous(
        state: State):  # Qui inseriremo la logica dove verifichiamo se è una domanda o un'affermazione da mettere a DB
    client = genai.Client(api_key=gemini_api_key)
    question = state["messages"][-1].content
    system_message_1 = (
        f"""Input: una frase in lingua naturale.

        Istruzioni:  
        1. Analizza la frase e individua eventuali ambiguità sintattiche, cioè quando un complemento, preposizione o modificatore può riferirsi a più elementi della frase, cambiando il significato.  
        2. Genera tutte le possibili combinazioni della frase chiarendo il ruolo di ciascun elemento (chi usa cosa, chi possiede cosa, ecc.).  
        3. Mantieni le frasi concise e naturali.
        4. L'output deve essere in formato JSON
        5. Se non rilevi nessuna ambiguità inserisci nella lista ambiguita l'unica interpretazione che hai dedotto
        Regole:
        Non aggiungere alcun commento, genera solo l'output.

        Formato di output JSON:  

        {{
      "frase": "<frase originale>",
      "ambiguita": [
        "<interpretazione alternativa 1>",
        "<interpretazione alternativa 2>",
        ...
      ]
    }}

        ...
        ---

        **Esempio:**  

        Frase: "Luigi guarda Marco con il binocolo"

        Ambiguità: 
        {{
      "frase": "Luigi guarda Marco con il binocolo",
      "ambiguita": [
        "Luigi guarda Marco usando il binocolo.",
        "Luigi guarda Marco, che possiede un binocolo."
      ]
    }}

    Frase: "Luca apre la finestra"
        Ambiguita:
        {{
      "frase": "Luca apre la finestra",
      "ambiguita": ["Luca apre una finestra"]
    }}


        Frase: {question}
        \n\n
        Ambiguità:
            """
    )

    # Usa genai.chat invece di client.models.generate_content
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[system_message_1]
    )
    new_text = result.text
    clean_output = re.sub(r"^```json\s*|\s*```$", "", new_text.strip(), flags=re.DOTALL)
    dati = json.loads(clean_output)
    # Accedo al campo "ambiguita"
    ambiguita = list(dati["ambiguita"])
    ambig = dati["ambiguita"]
    ambiguita.append("")
    return {"ambig_sent": ambiguita, "ambig_sent_tot": ambig}


async def insert_ambiguous_sent(state: State):
    frasi_ambigue = state["ambig_sent"]
    print("Le frasi ambigue sono:\n ", frasi_ambigue)
    frase_ambigua = InterpretationMessage(content=frasi_ambigue.pop(0),
                                          interpretation_type="semantic_disambiguation")  # SystemMessage(content=frasi_ambigue.pop(0))
    print("Frase ambigua selezionata:\n ", frase_ambigua)
    return {"ambig_sent": frasi_ambigue, "messages": [frase_ambigua]}


async def askForClarification(state: State):
    print("Chiedo chiarificazioni all'utente per queste frasi ambigue: \n", state["ambig_sent_tot"])
    frasi_ambigue = state["ambig_sent_tot"]
    client = genai.Client(api_key=gemini_api_key)
    system_message = (
        f"""Ti verrà fornito un elenco di frasi ambigue, il tuo compito sarà quello di generare una domanda ad un ipotetico utente per chiedergli chiarimenti o delucidazioni
        Regole: Non aggiungere nessun commento, genera solo la domanda da porre all'ipotetico utente.
            \n
            Esempio:
            Frasi: ["Luca guarda il cane che possiede gli occhiali", "Luca guarda il cane usando gli occhiali"]
            Domanda: Non mi è chiaro, Luca usa gli occhiali o il cane possiede gli occhiali?
            \n\n
            Frasi: {frasi_ambigue}
            Domanda: 
                            """
    )
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[system_message]
    )
    new_text = result.text
    query = f"""
                MERGE (sent:SENTENCE {{text: $sentence}})
                MERGE (a:AGENT {{name:"System"}})
                MERGE (a)-[:ASK_FOR_CLARIFICATION]->(sent)

                """

    params = {
        "sentence": new_text
    }

    neo4j_graph.query(query, params=params)
    print("System: ", new_text)
    clarify_question = SystemMessage(content=new_text)
    return {"messages": [clarify_question]}


async def userResponse(state: State):
    msg = state["messages"]
    text_user = input("User: ")
    return {"messages": [text_user]}


def clarification(state: State):
    frasi_ambigue = state["ambig_sent_tot"]
    domanda_chiarificazione = state["messages"][-2].content
    chiarificazione_utente = state["messages"][-1].content
    frase_selezionata = state["ambig_sent"]
    client = genai.Client(api_key=gemini_api_key)
    system_message = (
        f"""Ti verrà fornito un elenco di frasi ambigue, una domanda di chiarificazione e una risposta di chiarificazione.
        Il tuo compito sarà quello di scegliere dall'elenco delle frasi ambigue la frase corretta in base alla risposta di chiarificazione.
        Regole: Non aggiungere nessun commento, genera solo la frase selezionata.
        Se la risposta di chiarificazione non chiarisce l'ambiguità restituisci: AMBIGUITA NON RISOLTA
            \n
            Esempio:
            Elenco frasi ambigue: ["Luca guarda il cane che possiede gli occhiali", "Luca guarda il cane usando gli occhiali"]
            Domanda di chiarificazione: Non mi è chiaro, Luca usa gli occhiali o il cane possiede gli occhiali?
            Risposta di chiarificazione: è Luca che sta usando gli occhiali
            Frase selezionata: "Luca guarda il cane usando gli occhiali"
            \n
            Elenco frasi ambigue: ["La vecchia porta sbarra il passaggio", "Una signora anziana porta una sbarra"]
            Domanda di chiarificazione: Non mi è chiaro, la porta vecchia sbarra il passaggio o una signora vecchia porta una sbarra?
            Risposta di chiarificazione: è la vecchia che sbarra il passaggio
            Frase selezionata: AMBIGUITA NON RISOLTA
            \n\n
            Elenco frasi ambigue: {frasi_ambigue}
            Domanda di chiarificazione: {domanda_chiarificazione}
            Risposta di chiarificazione: {chiarificazione_utente}
            Frase selezionata:
                            """
    )
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[system_message]
    )
    new_text = result.text
    frase_selezionata.append(new_text)
    if "AMBIGUITA NON RISOLTA" not in new_text:
        try:
            ug.set_sentence(state["messages"][-1])
            frasi_ambigue.remove(new_text)
        except ValueError:
            frase_selezionata = [""]
    print("@frase selezionata: ", frase_selezionata)
    print("@frasi ambigue: ", frasi_ambigue)
    triple = state["tree"]
    print("@triple da eliminare: ")
    for frase in frasi_ambigue:
        print(triple[frase])
    return {"ambig_sent_tot": frasi_ambigue, "ambig_sent": frase_selezionata}


def deleteInterpretation(frase):
    query = """
            MATCH (n:INTERPRETATION {text:$frase})
            DETACH DELETE n

    """
    params = {"frase": frase}
    neo4j_graph.query(query, params=params)


def deleteTriple(triple):
    query = """WITH $trip AS trips
        UNWIND trips AS trip
        MATCH (e:ENTITY {name:trip[0]})
        MATCH (a:ACTION {name:trip[1]})
        OPTIONAL MATCH (c:COMPLEMENTS {name:trip[2]})
        OPTIONAL MATCH (e)-[r:ACTS]->(a)
        SET r.count = r.count - 1

        WITH trip, e, a, r

        CALL apoc.cypher.doIt(
          'OPTIONAL MATCH (n:ACTION {name:$startNodeName})-[d]->(m:COMPLEMENTS {name:$endNodeName})
           WHERE type(d)=$relType
           SET d.count = d.count - 1
           WITH d,n,m
           WHERE d.count <= 0
           DETACH DELETE d
           RETURN n.name AS from, m.name AS to',
          {relType: trip[3], startNodeName: trip[1], endNodeName: trip[2]}
        ) YIELD value
        RETURN e.name AS entity, a.name AS action, value"""
    params = {
        "trip": triple
    }
    neo4j_graph.query(query, params=params)
    query_delete_0_rel = """MATCH (n)-[r]->(m)
    WHERE r.count <= 0
    DETACH DELETE r"""
    neo4j_graph.query(query_delete_0_rel)


async def removeFromGraph(state: State):
    frasi_ambigue = state["ambig_sent_tot"]
    triple = state["tree"]
    for frase in frasi_ambigue:
        deleteTriple(triple[frase])
        deleteInterpretation(frase)
    domanda_iniziale = state["user_question"]
    deleteTriple(triple[domanda_iniziale])


# async def removeAmbiguousSentences(state:State):
#


async def dummyDispatcherNode(state: State):
    print("Instrado la seguente frase ai nodi per l'inserimento: ", state["messages"][-1])
    return


async def chatbot_answer(state: State):
    client = genai.Client(api_key=gemini_api_key)
    question = state["messages"][-1].content
    system_message = (
        f"""Rispondi alla domanda senza usare pronomi, utilizza esplicitamente le entità a cui ti riferisci.
        Regole: Non aggiungere nessun commento, rispondi solo alla domanda.
        Esempio:
        Domanda: Bere vino fa bene alla salute?
        Risposta: No, bere il vino non fa bene alla salute
        Domanda: Gli elefanti di che colore sono?
        Risposta: Gli elefanti sono di colore grigio
        \n
        Domanda: {question}
        Risposta:
                        """
    )
    result = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[system_message]
    )
    new_text = result.text
    system_message = SystemMessage(content=new_text)
    return {"messages": [system_message]}


def chatbot_fill_db(state: State):
    print("Devi riempire il DB")
    return


def route_quesion(
        state: State,
):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    question = state.get("question", [])
    if question:
        return "chatbot_answer"
    else:
        return "chatbot_fill_db"


def route_chatbot(
        state: State,
):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    if isinstance(state["messages"][-1], HumanMessage):
        return "chatbot_ambiguous"
    else:
        if len(state["ambig_sent"]) > 0:
            return "insert_ambiguous_sent"
        else:
            return END


def route_ambiguous(
        state: State,
):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    if len(state["ambig_sent"]) > 1:
        return "insert_ambiguous_sent"
    else:
        return "chatbot_init"


def route_insert_ambiguous(
        state: State,
):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    if len(state["ambig_sent"]) > 0:
        return "dummyDispatcherNode"
    else:
        if len(state["ambig_sent_tot"]) <= 1:
            return "chatbot_init"
        return "askForClarification"


graph_builder = StateGraph(State)

graph_builder.add_node('init', init)
graph_builder.add_node('updateGraph', updateGraph)
graph_builder.add_node('chatbot_init', chatbot_init)
graph_builder.add_node('chatbot_answer', chatbot_answer)
graph_builder.add_node('chatbot_fill_db', chatbot_fill_db)
graph_builder.add_node('chatbot_ambiguous', chatbot_ambiguous)
graph_builder.add_node('insert_ambiguous_sent', insert_ambiguous_sent)
graph_builder.add_node('askForClarification', askForClarification)
graph_builder.add_node('dummyDispatcherNode', dummyDispatcherNode)
graph_builder.add_node('userResponse', userResponse)
graph_builder.add_node('clarification', clarification)
graph_builder.add_node('removeFromGraph', removeFromGraph)

graph_builder.add_conditional_edges(
    "chatbot_init",
    route_quesion,
    {"chatbot_answer": "chatbot_answer", "chatbot_fill_db": "chatbot_fill_db"},
)

graph_builder.add_conditional_edges(
    "updateGraph",
    route_chatbot,
    {"chatbot_ambiguous": "chatbot_ambiguous", "insert_ambiguous_sent": "insert_ambiguous_sent", END: END},
)

graph_builder.add_conditional_edges(
    "chatbot_ambiguous",
    route_ambiguous,
    {"chatbot_init": "chatbot_init", "insert_ambiguous_sent": "insert_ambiguous_sent"},
)

graph_builder.add_conditional_edges(
    "insert_ambiguous_sent",
    route_insert_ambiguous,
    {"dummyDispatcherNode": "dummyDispatcherNode", "askForClarification": "askForClarification",
     "chatbot_init": "chatbot_init"},
)

graph_builder.add_edge(START, "init")
graph_builder.add_edge("init", "updateGraph")
graph_builder.add_edge("chatbot_answer", "updateGraph")
graph_builder.add_edge("dummyDispatcherNode", "updateGraph")
graph_builder.add_edge("askForClarification", "userResponse")
graph_builder.add_edge("userResponse", "clarification")
graph_builder.add_edge("clarification", 'removeFromGraph')
graph_builder.add_edge("removeFromGraph", 'chatbot_init')

graph = graph_builder.compile()

try:
    img_bytes = graph.get_graph().draw_mermaid_png()  # salva su file
    with open("new_graph_schema.png", "wb") as f:
        f.write(img_bytes)
except Exception as e:
    (
        print("⚠️ Errore durante il salvataggio:", e))


async def run_graph():
    # Stato iniziale vuoto
    initial_state = {}

    # Opzionale: puoi abilitare il tracciamento LangSmith se vuoi
    config = {
        # "configurable": {"thread_id": "some_id"},  # se vuoi abilitare il tracciamento
    }

    # Esegui il grafo (passando lo stato iniziale e il config)
    final_state = await graph.ainvoke(initial_state, config=config)



if __name__ == '__main__':
    asyncio.run(run_graph())
