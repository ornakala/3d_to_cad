# 3D to CAD Converter API

This is a FastAPI application that converts 3D mesh files (STL, OBJ) to CAD files (STEP) using FreeCAD.

## Prerequisites

1.  **Python 3.8+**
2.  **FreeCAD**: Must be installed on the system. The application looks for `FreeCADCmd.exe` in standard installation directories.
    *   If FreeCAD is installed in a non-standard location, set the `FREECAD_CMD` environment variable to the full path of `FreeCADCmd.exe`.

## Installation

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Running the API

Start the server:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Usage

### Convert a File

**Endpoint:** `POST /convert`

**Body:** `multipart/form-data` with a file field named `file`.

**Example using curl:**

```bash
curl -X POST -F "file=@example.stl" http://127.0.0.1:8000/convert --output example.step
```

## How it Works

1.  The user uploads an STL or OBJ file.
2.  The server saves it temporarily.
3.  A FreeCAD Python script is executed via `FreeCADCmd.exe`.
4.  The script:
    *   Imports the mesh.
    *   Performs smart repairs (harmonizes normals, removes non-manifolds, fixes self-intersections, fills holes).
    *   Converts the mesh to a Shape.
    *   Converts the Shape to a Solid.
    *   Refines the Solid.
    *   Exports to STEP format.
5.  The converted STEP file is returned to the user.
