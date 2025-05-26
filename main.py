import os
from pypdf import PdfReader
from dotenv import load_dotenv
from openai import OpenAI

# TODO
# 引入线程池并发优化

# Load environment variables
load_dotenv()
API_KEY : str = os.getenv("API_KEY")
API_BASE : str = os.getenv("API_BASE")
MODEL_NAME : str = os.getenv("MODEL_NAME")

# DIR
PAPERS_DIR : str = "./papers"
OUTPUT_DIR : str = "./output"


def extract_text_from_pdf(pdf_path, max_pages=3):
    """Extract text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages[:max_pages]:
        text += page.extract_text()
    return text

def output_text_from_pdf(file_name,text):
    base_name = os.path.splitext(file_name)[0]
    # Write text to a file which its name is file_name
    with open(OUTPUT_DIR + "/" + base_name + ".markdown", "w",encoding="utf-8") as f:
        f.write(text)
    f.close()


def summarize_paper(text):
    """Summarize a paper."""
    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "你是一个论文总结专家，请用中文总结。接下来我会不断给定你一些内容，请你使用markdown格式总结出各个分论点小标题。并且提出相应扩展。"
            },
            {
                "role": "user",
                "content": text
            }
        ],
        temperature=0.7,
        max_tokens=4096
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    # If the folder is not exists, create it
    os.makedirs(PAPERS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Loading pdf'name from papers folder
    file_list = [file for file in os.listdir(PAPERS_DIR) if file.endswith(".pdf")]    # Very impressing!
    print(file_list)

    length = len(file_list)

    time = 0
    for file_name in file_list:
        time += 1
        print("Please waiting, mission progress: " + str(time) + "/" + str(length)) 
        pdf_path = PAPERS_DIR + "/" + file_name
        text : str = extract_text_from_pdf(pdf_path)
        summary : str = summarize_paper(text)
        output_text_from_pdf(file_name,summary) 
        
    print("Mission completed!")