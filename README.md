# AI Agents for Ambiguity Resolution and Question Answering on Knowledge Graphs

This project implements AI agents capable of performing context-aware question answering and disambiguation over knowledge graphs using **LangGraph** and Neo4j. The system represents conversation states, manages ambiguities, and updates the knowledge graph based on user feedback.

---

## Conversation State Representation

The system represents both the **semantic** and **syntactic** structure of user inputs within LangGraph, allowing the chatbot to track conversation states precisely.

**Example Interaction:**

**User:** Posso prendere la tachipirina dopo i pasti?

**System:** La tachipirina può essere presa dopo i pasti.

Generated graph:

<img width="1301" height="846" alt="Conversation graph example" src="https://github.com/user-attachments/assets/3958dfb6-31ca-4f62-b8e5-6ef4e1bfb101" />

The system currently generates responses directly from the LLM for testing purposes, with the database integration (from Antonio Di Geronimo) planned for the next stage.

---

## LangGraph Structure

LangGraph handles both simple Q&A and updates to the knowledge graph.

Graph structure example:

<img width="536" height="743" alt="LangGraph structure" src="https://github.com/user-attachments/assets/aae0e715-8e39-4879-8a5f-7e5f0b3eeb56" />

---

## Ambiguity Detection

The system can detect ambiguous sentences, generate all possible interpretations, and add them to the conversation graph. If multiple interpretations exist, the chatbot asks for clarification.

**Example:**
*"Anna guarda Francesco mentre attraversa la strada"*

* Interpretation 1: Anna sta attraversando la strada.
* Interpretation 2: Francesco sta attraversando la strada.

Graphs for each interpretation:

<img width="1416" height="877" alt="Anna crosses street" src="https://github.com/user-attachments/assets/40a4155e-c2bc-4ac7-a0f9-d8e7ac190942" />  
<img width="1416" height="877" alt="Francesco crosses street" src="https://github.com/user-attachments/assets/d2405f64-115c-4732-aa98-a8b6eb23f513" />

**Clarification Question:**
*"Non ho capito, chi sta attraversando la strada Anna o Francesco?"*

<img width="1416" height="877" alt="Clarification question" src="https://github.com/user-attachments/assets/d8c23f58-9b56-4ead-8695-473faff0eb54" />

LangGraph structure for ambiguity detection:

<img width="784" height="622" alt="LangGraph ambiguity structure" src="https://github.com/user-attachments/assets/00e12489-0ab1-49b6-a708-536b03036a0d" />

---

## Disambiguation and Graph Update

Once the user provides clarification, the system updates the graph by **removing incorrect interpretations**.

**Example:**
*"Marco guarda Luca mentre attraversa la strada"*

Before clarification:

<img width="1350" height="648" alt="Ambiguous graph" src="https://github.com/user-attachments/assets/0b250bc4-ccae-4cb8-869d-abec4d14a142" />

User clarifies: *"Marco"*

After update:

<img width="1199" height="669" alt="Disambiguated graph" src="https://github.com/user-attachments/assets/c2d01fab-11b4-4860-a50f-ea7f1696511e" />

The graph now reflects only the correct interpretation, and the incorrect branch is removed.

---

## Dialogue Management vs Knowledge Graph Update

The system separates **dialogue management** from **Neo4j knowledge graph updates**:

**Dialogue Management Graph:**

<img width="784" height="750" alt="Dialogue management graph" src="https://github.com/user-attachments/assets/3ec389cb-c02c-4a68-a0ac-fdb7b4efafe1" />

**Neo4j Graph Update:**

<img width="337" height="531" alt="Neo4j graph update" src="https://github.com/user-attachments/assets/612033e5-fcb4-40db-ac29-25165a75434e" />

This separation allows the system to maintain real-time conversation state while updating the persistent knowledge graph safely.

---
