from langchain_core.tools import tool
import requests
from bs4 import BeautifulSoup

@tool
def get_webpage_title(url: str) -> str:
    """Fetches the title of a webpage given its URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        else:
            return "No title found"
    except Exception as e:
        return f"Error: {str(e)}"