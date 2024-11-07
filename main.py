import ollama
import chromadb
import logging
import os
from gtts import gTTS
import pygame
import tempfile
import time
import json
import random

# Configuración del logger
logging.basicConfig(level=logging.INFO)

# Función para cargar o crear la configuración de semillas temáticas
def cargar_o_crear_seeds_config():
    try:
        with open('seeds_config.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Función para guardar la configuración de semillas temáticas
def guardar_seeds_config(config):
    with open('seeds_config.json', 'w') as file:
        json.dump(config, file)

# Función para obtener o generar una semilla para un tema
def obtener_semilla_tema(tema, seeds_config):
    if tema not in seeds_config:
        seeds_config[tema] = random.randint(0, 2**32 - 1)
        guardar_seeds_config(seeds_config)
    return seeds_config[tema]

# Función para cargar documentos de todos los archivos .txt en un directorio
def cargar_documentos(directorio):
    documentos = []
    try:
        for filename in os.listdir(directorio):
            if filename.endswith('.txt'):
                with open(os.path.join(directorio, filename), 'r', encoding='utf-8') as file:
                    documentos.extend(file.readlines())
        logging.info("Documentos cargados desde el directorio.")
    except Exception as e:
        logging.error(f"Error al cargar documentos: {e}")
    return [doc.strip() for doc in documentos]  # Limpia espacios en blanco

# Función para cargar embeddings de los temas desde un archivo JSON
def cargar_embeddings_temas():
    try:
        with open('embeddings_temas.json', 'r', encoding='utf-8') as file:
            temas_embeddings = json.load(file)
        logging.info("Embeddings de temas cargados con éxito desde embeddings_temas.json.")
        return temas_embeddings
    except Exception as e:
        logging.error(f"Error al cargar embeddings de temas: {e}")
        return {}

# Función para guardar embeddings de los temas en un archivo JSON
def guardar_embeddings_temas(temas_embeddings):
    try:
        with open('embeddings_temas.json', 'w', encoding='utf-8') as file:
            json.dump(temas_embeddings, file, ensure_ascii=False, indent=4)
        logging.info("Embeddings de temas guardados con éxito en embeddings_temas.json.")
    except Exception as e:
        logging.error(f"Error al guardar embeddings de temas: {e}")

# Función para generar incrustaciones para los documentos y los almacena en embeddings_temas.json
def generar_incrustaciones_y_almacenar(documents, tema):
    try:
        embedding_tema = ollama.embeddings(model="mxbai-embed-large", prompt=tema)["embedding"]
        temas_embeddings = cargar_embeddings_temas()
        temas_embeddings[tema] = embedding_tema
        guardar_embeddings_temas(temas_embeddings)
        logging.info(f"Embedding para el tema '{tema}' generado y almacenado.")
    except Exception as e:
        logging.error(f"Error al generar o almacenar el embedding del tema: {e}")

# Inicializar el cliente de ChromaDB
client = chromadb.Client()

# Función para generar y almacenar embeddings en ChromaDB
def generar_incrustaciones_y_almacenar_chromadb(documents):
    try:
        collection = client.get_or_create_collection(name="docs")
        for i, d in enumerate(documents):
            response = ollama.embeddings(model="mxbai-embed-large", prompt=d)
            embedding = response["embedding"]
            collection.add(
                ids=[str(i)],
                embeddings=[embedding],
                documents=[d]
            )
        logging.info("Embeddings generados y almacenados con éxito en ChromaDB.")
        return collection
    except Exception as e:
        logging.error(f"Error al generar o almacenar embeddings: {e}")
        return None

# Función para recuperar un documento relevante usando embeddings
def recuperar_documento_relevante(collection, prompt):
    try:
        response = ollama.embeddings(model="mxbai-embed-large", prompt=prompt)
        embedding = response["embedding"]
        results = collection.query(query_embeddings=[embedding], n_results=1)
        if not results['documents']:
            logging.warning("No se encontraron documentos relevantes.")
            return None
        data = results['documents'][0][0]
        logging.info(f"Documento recuperado: {data}")
        return data
    except Exception as e:
        logging.error(f"Error al recuperar el documento: {e}")
        return None

# Función para generar la respuesta usando el documento recuperado y TSP
def generar_respuesta(prompt, data, tema, seeds_config):
    try:
        semilla = obtener_semilla_tema(tema, seeds_config)
        response = ollama.generate(
            model="llama3.2", 
            prompt=f"Usa estos datos: {data}. Responde en este prompt: {prompt}",
            options={"seed": semilla}
        )
        logging.info(f"Respuesta generada con éxito usando la semilla {semilla} para el tema '{tema}'.")
        return response['response']
    except Exception as e:
        logging.error(f"Error al generar la respuesta: {e}")
        return None

# Función para convertir la respuesta en audio y reproducirla usando pygame
def reproducir_respuesta_en_voz(respuesta):
    try:
        tts = gTTS(respuesta, lang='es', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            audio_path = fp.name
        pygame.mixer.init()
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.quit()
        logging.info("Respuesta reproducida en voz con éxito.")
    except Exception as e:
        logging.error(f"Error al reproducir la respuesta en voz: {e}")

# Función principal
if __name__ == "__main__":
    directorio = "datos"  # Cambia esta ruta según sea necesario
    documentos = cargar_documentos(directorio)
    collection = generar_incrustaciones_y_almacenar_chromadb(documentos)
    
    # Cargar o crear la configuración de semillas temáticas
    seeds_config = cargar_o_crear_seeds_config()
    
    tema = "cartas"  # Este es un ejemplo de tema; cambia según sea necesario
    generar_incrustaciones_y_almacenar(documentos, tema)

    if collection:
        prompt = "Probabilidad de vida extraterrestre"
        data = recuperar_documento_relevante(collection, prompt)

        if data:
            respuesta = generar_respuesta(prompt, data, tema, seeds_config)
            print("Respuesta generada:\n", respuesta)
            reproducir_respuesta_en_voz(respuesta)
