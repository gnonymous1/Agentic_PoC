"""
SEPE — Sovereign Executive Proxy Engine
Sandbox Subsystem Simulator — DECOMMISSIONED

=============================================================================
PRODUCTION TRANSITION MANIFEST
=============================================================================
The GNONE workspace has been successfully transitioned to a 100% real, active 
production deployment. Simulated in-memory loops and mock database fallbacks
have been removed to ensure absolute operational security and direct API dispatches.

To launch the real production cluster (FastAPI web server + Node A background observers):
Run:
    $ export SEPE_MASTER_KEY="your_32_byte_master_hex_key"
    $ export GEMINI_API_KEY="your_production_gemini_key"
    $ export OPENROUTER_API_KEY="your_production_openrouter_key"
    $ export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname"
    
    $ uvicorn main:app --host 0.0.0.0 --port 8000
=============================================================================
"""
import sys

if __name__ == "__main__":
    print(__doc__)
    sys.exit(0)
