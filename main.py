from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import os
import app.ChatbotInteraction as ci

load_dotenv()

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")
api_key = os.getenv("GEMINI_API_KEY")

def run_entity_extraction(sentence: str):
    """
    Funzione principale del sistema
    """
    ci.run_pipeline(uri, user, password, api_key, sentence)


if __name__ == '__main__':
    sample_sentence = ("")  #Se stringa vuota, attiva il sistema con input da tastiera
    run_entity_extraction(sample_sentence)