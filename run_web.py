#!/usr/bin/env python3
import sys
sys.path.insert(0, "src")
import uvicorn
uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
