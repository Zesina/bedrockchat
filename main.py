import base64
import boto3
import json
import os
import threading
import requests
import streamlit as st
from langchain.chains import LLMChain
from langchain.llms.bedrock import Bedrock
from langchain.prompts import PromptTemplate
import time
from dotenv import load_dotenv
from flask import Flask, request

app = Flask(__name__)

@app.route('/healthz')
def health_check():
    return "OK", 200


user_sessions = {}
# Load environment variables from .env file
load_dotenv()

# Set up Telegram bot
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"

# Bedrock client
bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1"
)

# Model IDs for text and image generation
text_model_id = "amazon.titan-text-premier-v1:0"
image_model_id = "amazon.titan-image-generator-v2:0"

# LLM for text generation
llm_text = Bedrock(
    model_id=text_model_id,
    client=bedrock_client,
    model_kwargs={"maxTokenCount": 2000, "temperature": 0.9}
)

# Function for generating chat responses
def my_chatbot(language, freeform_text):
    prompt = PromptTemplate(
        input_variables=["language", "freeform_text"],
        template="You are a chatbot for RBSMTC Khandari college. Made by MCA 3rd sem student name Gagan, You are in {language}.\n\n{freeform_text}"
    )

    bedrock_chain = LLMChain(llm=llm_text, prompt=prompt)

    response = bedrock_chain({'language': language, 'freeform_text': freeform_text})
    return response['text']

# Function for generating images
def create_image(input_text):
    image_config = {
        "textToImageParams": {"text": input_text},
        "taskType": "TEXT_IMAGE",
        "imageGenerationConfig": {
            "cfgScale": 8.0,
            "seed": 0,
            "quality": "standard",
            "width": 576,
            "height": 384,
            "numberOfImages": 1
        }
    }

    try:
        response = bedrock_client.invoke_model(
            modelId=image_model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(image_config)
        )

        time.sleep(60)

        response_body = json.loads(response['body'].read())

        if 'images' in response_body:
            image_data_base64 = response_body['images'][0]
            image_data = base64.b64decode(image_data_base64)
            return image_data
        else:
            return None
    except Exception as e:
        return None


# Telegram bot functions
def send_message(chat_id, text):
    url = TELEGRAM_URL + "sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=payload)
    print(f"send_message response: {response.json()}")

def handle_start(chat_id):
    send_message(chat_id, "Hello! I am online. Use /ask followed by your question.")

def handle_ask(chat_id, question):
    if chat_id in user_sessions:
        user_sessions[chat_id].append(question)
    else:
        user_sessions[chat_id] = [question]
    
    # Simulate a delay to make it feel more human-like
    time.sleep(2)  # Adjust the delay as needed

    language = "english"
    response_text = my_chatbot(language, question)
    send_message(chat_id, response_text)
    print(f"Question from {chat_id}: {question}")
    print(f"Response to {chat_id}: {response_text}")

def handle_image(chat_id, text):
    image_data = create_image(text)
    if image_data:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        files = {"photo": image_data}
        data = {"chat_id": chat_id, "caption": "Generated Image"}
        response = requests.post(url, files=files, data=data)
        print(f"sendPhoto response: {response.json()}")
    else:
        send_message(chat_id, "Failed to generate image.")

def get_updates(offset=None):
    url = TELEGRAM_URL + "getUpdates"
    params = {"timeout": 100, "offset": offset}
    response = requests.get(url, params=params)
    return response.json()

def handle_updates(updates):
    for update in updates["result"]:
        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"]["text"]

            if text.startswith("/start"):
                handle_start(chat_id)
            elif text.startswith("/ask"):
                question = text[len("/ask "):]
                handle_ask(chat_id, question)
            elif text.startswith("/image"):
                image_text = text[len("/image "):]
                handle_image(chat_id, image_text)
            else:
                send_message(chat_id, "Are Bro...tum bhi na.. 👻 Use /ask followed by your question or /image followed by the text for the image.")

def run_telegram_bot():
    offset = None
    while True:
        updates = get_updates(offset)
        if "result" in updates and updates["result"]:
            handle_updates(updates)
            offset = updates["result"][-1]["update_id"] + 1

# Start the Telegram bot polling in a separate thread
telegram_thread = threading.Thread(target=run_telegram_bot)
telegram_thread.start()


# Streamlit UI enhancements
st.set_page_config(page_title="Gen Chatbot 🤖", page_icon=":robot_face:", layout="centered")
st.image("logo.png", width=100)

st.title("RBS Chatbot 🤖")

language = st.sidebar.selectbox("Language", ["english", "hindi"])

suggested_questions = [
    "What is the capital of France?",
    "Who is Buddha?"
]

if language:
    st.sidebar.write("Suggested Questions:")
    for question in suggested_questions:
        if st.sidebar.button(question):
            freeform_text = question
            response = my_chatbot(language, freeform_text)
            st.write(response)

    st.markdown("<h3 style='text-align: left; color: gold;'>What is your question?</h3>", unsafe_allow_html=True)
    freeform_text = st.text_area(label="", max_chars=100)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Ask"):
            if freeform_text:
                response = my_chatbot(language, freeform_text)
                st.write(response)
    with col2:
        if st.button("Create Image"):
            if freeform_text:
                with st.spinner('Generating image...'):
                    image_data = create_image(freeform_text)
                    if image_data:
                        st.image(image_data, caption="Generated Image")
                    else:
                        st.error("Failed to generate image.")

# To run: python -m streamlit run main.py
