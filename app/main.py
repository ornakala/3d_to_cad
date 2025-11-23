import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="3D to CAD Converter")

# Configuration for FreeCAD path
FREECAD_CMD = os.getenv("FREECAD_CMD")

def find_freecad():
    global FREECAD_CMD
    if FREECAD_CMD:
        # Always convert to absolute path to avoid issues with subprocess and shell=True
        abs_path = os.path.abspath(FREECAD_CMD)
        if os.path.exists(abs_path):
            FREECAD_CMD = abs_path
            return abs_path
            
        # Fallback: check if the relative path exists (though abspath should cover this)
        if os.path.exists(FREECAD_CMD):
            return os.path.abspath(FREECAD_CMD)
            
    # Common paths to check
    possible_paths = [
        r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.22\bin\FreeCADCmd.exe", 
        r"C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.19\bin\FreeCADCmd.exe",
        r"C:\Program Files (x86)\FreeCAD 0.21\bin\FreeCADCmd.exe",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            FREECAD_CMD = path
            return path
            
    # If not found, check PATH
    shutil_path = shutil.which("FreeCADCmd")
    if shutil_path:
        FREECAD_CMD = shutil_path
        return shutil_path
        
    return None

def remove_file(path: str):
    try:
        os.remove(path)
    except Exception:
        pass

@app.on_event("startup")
async def startup_event():
    cmd = find_freecad()
    if cmd:
        print(f"Found FreeCAD at: {cmd}")
    else:
        print("WARNING: FreeCADCmd.exe not found. Conversion will fail unless FREECAD_CMD environment variable is set.")

@app.post("/convert")
async def convert_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Convert a 3D mesh file (STL/OBJ) to a CAD file (STEP).
    The conversion is 'smart' - it attempts to repair the mesh and convert it to a solid.
    """
    if not file.filename.lower().endswith(('.stl', '.obj')):
        raise HTTPException(status_code=400, detail="Only .stl and .obj files are supported.")
    
    cmd = find_freecad()
    if not cmd:
        raise HTTPException(status_code=500, detail="FreeCAD executable not found on server. Please install FreeCAD or set FREECAD_CMD.")

    # Warn if using GUI executable
    if "FreeCAD.exe" in os.path.basename(cmd) and "FreeCADCmd.exe" not in os.path.basename(cmd):
        print("WARNING: You are using 'FreeCAD.exe' (GUI) instead of 'FreeCADCmd.exe' (Console). This may cause issues or require elevation. Please use 'FreeCADCmd.exe' if possible.")

    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, file.filename)
        # Ensure input path uses forward slashes for Python string compatibility in generated script
        input_path = input_path.replace("\\", "/")
        
        output_filename = os.path.splitext(file.filename)[0] + ".step"
        output_path = os.path.join(temp_dir, output_filename)
        output_path = output_path.replace("\\", "/")
        
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Create a temporary python script that has the paths hardcoded
        # This avoids passing arguments to FreeCADCmd which can be misinterpreted as files to open
        converter_logic_path = os.path.join(os.path.dirname(__file__), "converter_script.py").replace("\\", "/")
        
        wrapper_script_content = f"""
import sys
import os

# Add the app directory to path so we can import the converter logic
sys.path.append("{os.path.dirname(converter_logic_path)}")

import converter_script

try:
    converter_script.convert("{input_path}", "{output_path}")
except Exception as e:
    print(f"Wrapper Error: {{e}}")
    sys.exit(1)
"""
        wrapper_script_path = os.path.join(temp_dir, "run_conversion.py")
        with open(wrapper_script_path, "w") as f:
            f.write(wrapper_script_content)
        
        # Run FreeCAD conversion using the wrapper script
        # Command: FreeCADCmd.exe run_conversion.py
        command_str = f'"{cmd}" "{wrapper_script_path}"'
        print(f"Running conversion: {command_str}")
        
        try:
            process = subprocess.run(
                command_str,
                capture_output=True,
                text=True,
                check=False,
                shell=True,
                encoding='utf-8', 
                errors='replace' # Handle potential encoding errors in FreeCAD output
            )
            
            # Log output for debugging
            if process.stdout:
                print(f"FreeCAD Stdout: {process.stdout}")
            if process.stderr:
                print(f"FreeCAD Stderr: {process.stderr}")
            
            if process.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Conversion process failed. Logs: {process.stderr}")
                
            if not os.path.exists(output_path):
                # Check if maybe it failed silently or output was redirected
                raise HTTPException(status_code=500, detail="Conversion failed: Output file was not created. The mesh might be too complex or invalid.")
                
            # Copy to a persistent temp location to return it
            fd, final_temp_path = tempfile.mkstemp(suffix=".step")
            os.close(fd)
            shutil.copy(output_path, final_temp_path)
            
            # Schedule cleanup
            background_tasks.add_task(remove_file, final_temp_path)
            
            return FileResponse(
                final_temp_path, 
                filename=output_filename, 
                media_type="application/STEP"
            )
            
        except Exception as e:
            print(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=str(e))
