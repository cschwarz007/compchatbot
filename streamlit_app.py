import streamlit as st
import hmac
import langchain
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.llms import OpenAI
from langchain.chains import VectorDBQA
from langchain.chains import RetrievalQAWithSourcesChain
import PyPDF2

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if check_password is not True.

#This function will go through pdf and extract and return list of page texts.
def read_and_textify(files):
    text_list = []
    sources_list = []
    for file in files:
        pdfReader = PyPDF2.PdfReader(file)
        #print("Page Number:", len(pdfReader.pages))
        for i in range(len(pdfReader.pages)):
          pageObj = pdfReader.pages[i]
          text = pageObj.extract_text()
          pageObj.clear()
          text_list.append(text)
          sources_list.append(file.name + "_page_"+str(i))
    return [text_list,sources_list]

st.set_page_config(layout="centered", page_title="Compliance ChatBot - TEST")
st.header("ComplianceChatBot")
st.write("---")
  
#file uploader
uploaded_files = st.file_uploader("Upload documents",accept_multiple_files=True, type=["txt","pdf"])
st.write("---")

if uploaded_files is None:
  st.info(f"""Upload files to analyse""")
elif uploaded_files:
  st.write(str(len(uploaded_files)) + " document(s) loaded..")
  
  textify_output = read_and_textify(uploaded_files)
  
  documents = textify_output[0]
  sources = textify_output[1]
  
  #extract embeddings
  embeddings = OpenAIEmbeddings(openai_api_key = st.secrets["openai_api_key"])
  #vstore with metadata. Here we will store page numbers.
  vStore = Chroma.from_texts(documents, embeddings, metadatas=[{"source": s} for s in sources])
  #deciding model
  model_name = "gpt-3.5-turbo"
  # model_name = "gpt-4"

  retriever = vStore.as_retriever()
  retriever.search_kwargs = {'k':2}

  #initiate model
  llm = ChatOpenAI(model_name=model_name, openai_api_key = st.secrets["openai_api_key"], streaming=True)
  model = RetrievalQAWithSourcesChain.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
  
  st.header("Ask your data")
  user_q = st.text_area("Enter your questions here")
  
  if st.button("Get Response"):
    try:
      with st.spinner("Model is working on it..."):
        result = model({"question":user_q}, return_only_outputs=True)
        st.subheader('Your response:')
        st.write(result['answer'])
        st.subheader('Source pages:')
        st.write(result['sources'])
    except Exception as e:
      st.error(f"An error occurred: {e}")
      st.error('Oops, the GPT response resulted in an error :( Please try again with a different question.')
