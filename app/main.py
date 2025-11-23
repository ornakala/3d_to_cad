import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

app = FastAPI(title="3D to CAD Converter")

# Configuration for FreeCAD path
FREECAD_CMD = os.getenv("FREECAD_CMD")

def find_freecad():
    global FREECAD_CMD
    if FREECAD_CMD and os.path.exists(FREECAD_CMD):
        return FREECAD_CMD
    
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

    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, file.filename)
        output_filename = os.path.splitext(file.filename)[0] + ".step"
        output_path = os.path.join(temp_dir, output_filename)
        
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Path to converter script
        script_path = os.path.join(os.path.dirname(__file__), "converter_script.py")
        
        # Run FreeCAD conversion
        print(f"Running conversion: {cmd} {script_path} {input_path} {output_path}")
        try:
            process = subprocess.run(
                [cmd, script_path, input_path, output_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            # Log output for debugging
            if process.stdout:
                print(f"FreeCAD Stdout: {process.stdout}")
            if process.stderr:
                print(f"FreeCAD Stderr: {process.stderr}")
            
            if process.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Conversion process failed. Logs: {process.stderr}")
                
            if not os.path.exists(output_path):
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
