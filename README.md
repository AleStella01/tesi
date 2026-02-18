The "chat.py" file is a script that allows you to connect the model to the chatUI application.
The "energy_api.py" file is the proxy server containing the CodeCarbon script for measurements, which runs on port 9000.
The model is a LLAMA-based model, which runs on port 8080.
The chatUI application is "Hugging Face ChatUI" and runs on the port 5173.
The MongoDB server runs on the port 27017.
All architecture runs in a venv.

In the "commands.txt" file there are commands that allows to run all architecture.

The "env.local" file is the file that contains the local configurations of "ChatUI". In particular, it will be named within the chatUI directory like ".env.local".

The "package.json" file is one of the files inside the chatUI directory. The file must be configured as reported, so that the application can track the context through the MongoDB server.
