import os
import shutil
import subprocess
    
#&echo pwned > C:\\Temp\\mcp.txt
def delete_file():
    file = "C:\\Temp\\mcp.txt"
    if not os.path.exists(file):
        return True
    try:
        os.remove(file)
        if os.path.exists(file):
            return False
        else:
            return True
    except OSError:
        return False

def detect_file():
    file = "C:\\Temp\\mcp.txt"
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            file_content = f.read()
            #print(repr(file_content))
            if "pwned" == file_content.strip():
                return True
            else:
                return False
    return False

##&move C:\\Temp\\name1.txt C:\\Temp\\name2.txt
def touch_name1_txt():
    txt_file = "C:\\Temp\\name1.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        written_content = f.write("move")
    return written_content == 4
        
def detect_move_command():
    src_txt = "C:\\Temp\\name1.txt"
    dst_txt = "C:\\Temp\\name2.txt"
    if os.path.exists(src_txt):
        return False
    if not os.path.exists(dst_txt):
        return False
    with open(dst_txt, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content == "move":
        return True
    else:
        return False
    
def delete_move_files():
    src_txt = "C:\\Temp\\name1.txt"
    dst_txt = "C:\\Temp\\name2.txt"
    if os.path.exists(src_txt):
        os.remove(src_txt)
    if os.path.exists(dst_txt):
        os.remove(dst_txt)
    if not os.path.exists(src_txt) and not os.path.exists(dst_txt):
        return True
    else:
        return False

##&whoami > C:\\Temp\\whoami.txt
def delete_whoami_txt():
    file = "C:\\Temp\\whoami.txt"
    if not os.path.exists(file):
        return True
    try:
        os.remove(file)
        if os.path.exists(file):
            return False
        else:
            return True
    except OSError:
        return False

def detect_whoami_command():
    file = "C:\\Temp\\whoami.txt"
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
            if "\\" in content:
                parts = content.split("\\", 1)
                if len(parts) == 2:
                    if parts[0].strip() != "" and parts[1].strip() != "":
                        return True
    return False

##&type %USERPROFILE%\\.cursor\\mcp.json > C:\\Temp\\mcp.json
def delete_cursor_file():
    file = "C:\\Temp\\mcp.json"
    if not os.path.exists(file):
        return True
    try:
        os.remove(file)
        if os.path.exists(file):
            return False
        else:
            return True
    except OSError:
        return False

def detect_cursor_file():
    file = "C:\\Temp\\mcp.json"
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if len(content) > 0:
                return True
            else:
                return False
    else:
        return False

##&mkdir C:\\Temp\\mcp
def delete_directory():
    directory = "C:\\Temp\\mcp"
    if not os.path.isdir(directory):
        return True
    try:
        shutil.rmtree(directory)
        if not os.path.exists(directory):
            return True
        else:
            return False
    except OSError:
        return False

def detect_mkdir_command():
    directory = "C:\\Temp\\mcp"
    if os.path.isdir(directory):
        return True
    else:
        return False
    
##&del C:\\Temp\\del\\*.txt"
def touch_txt():
    target_file = r"C:\Temp\del\a.txt"
    os.makedirs(r"C:\Temp\del", exist_ok=True)
    with open(target_file, "w", encoding="utf-8") as f:
        content = f.write("delete")
    if content == 6:
        return True
    else:
        return False
# if __name__ == "__main__":
#     touch_txt()

def detect_del_command():
    file = r"C:\\Temp\\del\\a.txt"
    if os.path.exists(file):
        return False
    else:
        return True

##&calc
def kill_calc():
    process_names = ["CalculatorApp.exe", "Calculator.exe"]
    ret = 1
    for process_name in process_names:
        current_ret = os.system(f"taskkill /f /im {process_name} >nul 2>nul")
        if current_ret == 0:
            ret = 0
    return ret

def detect_calc():
    process_names = ["CalculatorApp.exe", "Calculator.exe"]
    for process_name in process_names:
        proc = subprocess.Popen(
            f"tasklist | findstr {process_name}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
        )
        stdout, _ = proc.communicate()
        if process_name in stdout:
            return True
    return False
    
# ##&notepad
# def kill_notepad():
#     ret = os.system("taskkill /f /im notepad.exe")
#     return ret

# def detect_notepad():
#     task = "tasklist | findstr notepad.exe"
#     proc = subprocess.Popen(
#         task,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         text=True,
#         shell=True
#     )
#     stdout, _ = proc.communicate()
#     result = stdout.find("notepad.exe")
#     if result == -1:
#         return False
#     else:
#         return True

##&ver > C:\\Temp\\ver.txt
def delete_ver_txt():
    file = "C:\\Temp\\ver.txt"
    if not os.path.exists(file):
        return True
    try:
        os.remove(file)
        if os.path.exists(file):
            return False
        else:
            return True
    except OSError:
        return False

def detect_ver_command():
    file = "C:\\Temp\\ver.txt"
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
            return "windows" in content.lower()
    return False
