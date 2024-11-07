import ollama
import chromadb
import logging
import os
from gtts import gTTS
import pygame
import tempfile
import json
import random
import re
from functools import lru_cache
from typing import List, Optional

# Configuración del logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SeedManager:
    def __init__(self, config_file: str = 'seeds_config.json'):
        self.config_file = config_file
        self.seeds_config = self.load_config()

    def load_config(self) -> dict:
        try:
            with open(self.config_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_config(self) -> None:
        with open(self.config_file, 'w') as file:
            json.dump(self.seeds_config, file, indent=4)

    def get_seed(self, tema: str) -> int:
        if not tema:
            raise ValueError("El tema extraído está vacío.")
        if tema not in self.seeds_config:
            logging.info(f"Generando nueva semilla para el tema: {tema}")
            self.seeds_config[tema] = random.randint(0, 2**32 - 1)
            self.save_config()
        return self.seeds_config[tema]

class EmbeddingManager:
    def __init__(self, model: str = "mxbai-embed-large"):
        self.model = model
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(name="docs")

    @lru_cache(maxsize=100)
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        try:
            response = ollama.embeddings(model=self.model, prompt=text)
            return response["embedding"]
        except Exception as e:
            logging.error(f"Error al generar embedding: {e}")
            return None

    def store_embedding(self, id: str, text: str, embedding: List[float]) -> None:
        try:
            self.collection.add(
                ids=[id],
                embeddings=[embedding],
                documents=[text]
            )
        except Exception as e:
            logging.error(f"Error al almacenar embedding: {e}")

    def query_similar(self, query_embedding: List[float], n_results: int = 1) -> Optional[List[str]]:
        try:
            results = self.collection.query(query_embeddings=[query_embedding], n_results=n_results)
            return results['documents'][0] if results['documents'] else None
        except Exception as e:
            logging.error(f"Error al consultar embeddings similares: {e}")
            return None

def cargar_documentos(directorio: str) -> List[str]:
    documentos = []
    try:
        for filename in os.listdir(directorio):
            if filename.endswith('.txt'):
                with open(os.path.join(directorio, filename), 'r', encoding='utf-8') as file:
                    documentos.extend(file.readlines())
        logging.info(f"Se cargaron {len(documentos)} documentos desde el directorio.")
    except Exception as e:
        logging.error(f"Error al cargar documentos: {e}")
    return [doc.strip() for doc in documentos if doc.strip()]

def extraer_tema(prompt: str) -> str:
    match = re.match(r"^(.*?)(probabilidad|estudio|información|cuál|cómo|por qué|que)\b", prompt, re.IGNORECASE)
    if match:
        tema = match.group(1).strip()
        logging.info(f"Tema extraído del prompt: {tema}")
        return tema
    return prompt.split()[0]

def generar_respuesta(prompt: str, data: str, seed_manager: SeedManager, model: str = "llama3.2") -> Optional[str]:
    try:
        tema = extraer_tema(prompt)
        if not tema:
            raise ValueError("El tema extraído está vacío.")
        semilla = seed_manager.get_seed(tema)
        response = ollama.generate(
            model=model,
            prompt=f"Usa estos datos: {data}. Responde en este prompt: {prompt}",
            options={"seed": semilla}
        )
        logging.info(f"Respuesta generada con éxito usando la semilla {semilla} para el tema '{tema}'.")
        return response['response']
    except Exception as e:
        logging.error(f"Error al generar la respuesta: {e}")
        return None

def reproducir_respuesta_en_voz(respuesta: str) -> None:
    try:
        tts = gTTS(respuesta, lang='es', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            audio_path = fp.name
        
        pygame.mixer.init()
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.quit()
        
        os.remove(audio_path)
        logging.info("Respuesta reproducida en voz con éxito.")
    except Exception as e:
        logging.error(f"Error al reproducir la respuesta en voz: {e}")

def main():
    directorio = "datos"
    seed_manager = SeedManager()
    embedding_manager = EmbeddingManager()

    documentos = cargar_documentos(directorio)

    for i, doc in enumerate(documentos):
        embedding = embedding_manager.generate_embedding(doc)
        if embedding:
            embedding_manager.store_embedding(str(i), doc, embedding)

    while True:
        prompt = input("Ingrese su pregunta (o 'salir' para terminar): ")
        if prompt.lower() == 'salir':
            break

        query_embedding = embedding_manager.generate_embedding(prompt)
        
        if query_embedding:
            data = embedding_manager.query_similar(query_embedding)
            
            if data:
                respuesta = generar_respuesta(prompt, data[0], seed_manager)
                if respuesta:
                    print("Respuesta generada:\n", respuesta)
                    reproducir_respuesta_en_voz(respuesta)
                else:
                    print("No se pudo generar una respuesta.")
            else:
                print("No se encontraron documentos relevantes.")
        else:
            print("No se pudo generar el embedding para la consulta.")

if __name__ == "__main__":
    main()
