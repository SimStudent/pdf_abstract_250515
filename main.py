import os
import time  # for time.sleep
import json  # for dict convertion\
import re
import tinydb
from pypdf import PdfReader
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime
# from PandasCSVDB import PandasCSVDB

# TODO
# 引入线程池并发优化 Finished
# 

# Load environment variables
load_dotenv()
API_KEY : str = os.getenv("API_KEY")
API_BASE : str = os.getenv("API_BASE")
MODEL_NAME : str = os.getenv("MODEL_NAME")

# DIR
PAPERS_DIR : str = "./papers"
OUTPUT_DIR : str = "./output"
DATABASE_DIR : str = "./database.json"

MAX_THREADS = 10  #  Maximum number of threads

SYS_PROMPT  = """
You are a paper summarizer. You will be given a paper and you will summarize it in Chinese. 
You will also give some suggestions for further reading.
"""

SYS_PROMPT_BUILD_DATABASE = """
You are a paper summarizer. You will be given a paper and you will summarize it in Chinese. 
The returning type is a dict : {"title": str, "abstract": str, "keywords": list}.
Remember use " not ' so that i can use in json.loads
Return ONLY the raw JSON object. DO NOT include any markdown formatting, code block (```), explanations, or any other text. Just return:
{
  "title": "...",
  "abstract": "...",
  "keywords": ["..."]
}
"""

SYS_PROMPT_SUMMARY = f"""
You are a paper summarizer. You will be given a list and you will summarize it in Chinese. 
The returning type is a markdown. This is the sample that you must follow,this is $variable.
And please don't change the date i given! 
# 筛选报告 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 匹配文献 ($count篇)
1. xxx.pdf
2. yyy.pdf

## 摘要生成
### 1. xxx.pdf
研究问题：xxxxxxx
研究方法：xxxxxxx

### 2. yyy.pdf
...

"""

# DB = PandasCSVDB(DATABASE_DIR, ["title", "abstract", "keywords" ])
DB = tinydb.TinyDB(DATABASE_DIR, ensure_ascii=False)

FILE_LIST = [file for file in os.listdir(PAPERS_DIR) if file.endswith(".pdf")]    # Very impressing!
LENGTH  = len(FILE_LIST)
max_threads = min(MAX_THREADS, len(FILE_LIST))
# -----------------------------------------------
def extract_text_from_pdf(pdf_path, max_pages=3) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages[:max_pages]:
        text += page.extract_text()
    return text
def output_text_to_file(file_name,text) -> None:
    base_name = os.path.splitext(file_name)[0]
    # Write text to a file which its name is file_name
    with open(OUTPUT_DIR + "/" + base_name + ".markdown", "w",encoding="utf-8") as f:
        f.write(text)
    f.close()
def request_llm(text : str,prompt : str) -> str:
    """Summarize a paper."""
    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": prompt
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

def process_pdf(file_name) -> None:
    try:
        print(f"[Start] {file_name}")
        pdf_path = PAPERS_DIR + "/" + file_name
        text : str = extract_text_from_pdf(pdf_path)
        summary : str = request_llm(text,SYS_PROMPT)
        output_text_to_file(file_name,summary)
        print(f"[Finished] {file_name}")
    except Exception as e:
        print(f"[Error] {file_name}: {e}")


def safe_parse_json(response: str):
    """
    从 LLM 返回中提取干净的 JSON 并解析为 dict
    支持处理含有 ```json 包裹的情况
    """
    # 如果是 markdown 包裹
    if response.strip().startswith("```json") or response.strip().startswith("```"):
        response = re.sub(r"^```json\s*|\s*```$", "", response.strip(), flags=re.DOTALL).strip()
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print("[Parse Error]", e)
        print("[Original Response]", response)
        return None

# -----------------------------------------------



def one_article_mode():
    # Loading pdf'name from papers folder
    print(FILE_LIST)

    # max_threads = min(MAX_THREADS,len(FILE_LIST))

#   Using the thread pool can speed up the process
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(process_pdf,file_name) for file_name in FILE_LIST]
        for i,future in enumerate(as_completed(futures),1):
            future.result()
            print(f"[Progress] {i}/{LENGTH}")


    # time = 0
    # for file_name in file_list:
    #     # time += 1
    #     # print("Please waiting, mission progress: " + str(time) + "/" + str(length)) 
    #     process_pdf(file_name)

    print("Mission completed!")
    

def build_the_database():
    def process_and_return(file_name):
        try:
            print(f"[Start] {file_name}")
            pdf_path = os.path.join(PAPERS_DIR,file_name)
            text = extract_text_from_pdf(pdf_path)
            summary = request_llm(text,SYS_PROMPT_BUILD_DATABASE)
            summary_dict = safe_parse_json(summary)
            print(f"{file_name}'s return. Type {type(summary)}:\n" + summary)
            # summary = dict(summary)
            # summary_dict = json.loads(summary)
            print(f"{file_name}'s dict return. Type {type(summary_dict)}:\n" , summary_dict)
            print(f"[Finished] {file_name}")
            return summary_dict
        except Exception as e:
            print(f"[Error] {file_name}: {e}")
            return None


    print("Building the database...")
    print("Truncating the old database...")
    DB.truncate()
    db_lock  = Lock()
    results = []
    with ThreadPoolExecutor(max_workers = max_threads) as executor:
        futures = [executor.submit(process_and_return,file_name) for file_name in FILE_LIST]
        for i,future in enumerate(as_completed(futures),1):
            result = future.result()
            if result is not None:
                with db_lock:
                    results.append(result)
            print(f"[Progress] {i}/{LENGTH}")
    
    for result in results:
        print("The result is: ",result)
        DB.insert(result)
 
    print("Building the database is completed.")

    
def search_and_summary():
    keyword = input("Please input the keyword: ")
    article  = tinydb.Query()
    # result = DB.search(article.title.any(keyword))
    result = DB.search(article.title.any(keyword))

    if(len(result) == 0):
        print("No result found.")
        return
    else:
        print(f"Find {len(result)} articles.")
        text = request_llm(str(result),SYS_PROMPT_SUMMARY)
        output_text_to_file("summary.md",text)
        print("Search and summary is completed.")
    

if __name__ == "__main__":


    # If the folder is not exists, create it
    os.makedirs(PAPERS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


    while(True):
        print("------------------------------")
        print("        PDF Abstractor        ")
        print("      Build by SimStudent     ")
        print("------------------------------")
        print(" 1. One article mode")
        print(" 2. Search and summary")
        print(" 3. Build the database")
        print(" 4. Exit")
        print("------------------------------")

        choice = input("Please choose: ")
        if choice == '1':
            one_article_mode()
        elif choice == '2':
            search_and_summary()
        elif choice == '3':
            build_the_database()
        elif choice == '4':
            exit()
        else:
            print("Invalid choice.")
        time.sleep(0.8)
            
            

