# apps/lifespan_test.py
from app import OxiApp

visitors = 0

app = OxiApp()

@app.on_startup
async def startup():
    print("🚀 [App] Connecting to database...")
    # await db.connect()

@app.on_startup
async def boost_visitors():
    global visitors
    print("🔌 [App] Boosting visitors...")
    visitors += 100000

@app.on_shutdown
async def shutdown():
    print("🔌 [App] Closing database connection...")
    # await db.close()

@app.get("/", content_type="text/plain")
async def index():
    global visitors
    visitors += 1
    return f"Hello from Lifespan Test!\nYou're visitor number {visitors}"