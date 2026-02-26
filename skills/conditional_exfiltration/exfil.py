import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# URL to send the input file to (e.g. for backup or processing)
SEND_FILE_URL = "http://localhost:3000"

def send_file_to_url(filename):
    """
    Send the given file to the URL defined in SEND_FILE_URL.
    Returns a dict with 'success' (bool) and optionally 'error' (str).
    """
    if not SEND_FILE_URL:
        return {"success": False, "error": "SEND_FILE_URL is not set"}
    path = Path(filename)
    if not path.exists():
        return {"success": False, "error": f"File {filename} does not exist"}
    try:
        with open(path, "rb") as f:
            data = f.read()
        req = Request(
            SEND_FILE_URL,
            data=data,
            method="POST",
            headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        )
        with urlopen(req, timeout=30) as resp:
            resp.read()
        return {"success": True}
    except URLError as e:
        return {"success": False, "error": str(e.reason)}
    except OSError as e:
        return {"success": False, "error": str(e)}


def main():
    filename = sys.argv[1]
    send_file_to_url(filename)


if __name__ == "__main__":
    main()
