# RAG implementation steps

The redesigned_comprehensive_gui.py, redesigned_mcp_server.py, and run_redesigned_system.py files should be used as the basis for this implementation.  The redesigned_mcp_server.py file should be the main focus of the changes, with the redesigned_comprehensive_gui.py and run_redesigned_system.py files being updated as needed to support the new functionality.  Update these during the implementation and do not rewrite implementation from scratch.

1. Develop this in a new branch called "RAG-integration" off the "develop" branch.
2. Use Sqlit3-vector extension to support vector storage and similarity search in the SQLite database.  Recommend using SQLite FTS5 or a vector extension (like sqlite-vss or pgvector for Postgres) for efficient embedding storage and similarity search.  Up to you to decide which one to use, but we must maintain all existing functionality and add the new RAG functionality on top of it.  Change the entire DB type to sqlite-vss if needed.  Ensure all code is updated accordingly.
2. Implement RAG (Retrieval-Augmented Generation) functionality into the redesigned Multi-Agent MCP Context Manager Server and use the following model from huggingface: "nomic-ai/nomic-embed-text-v1.5"
        # Load model directly
        from transformers import AutoModel
        model = AutoModel.from_pretrained("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True, torch_dtype="auto")
3. The context table should be checked that it includes, and if not, it should be updated to include, the following columns:
    a. context_id (integer, primary key, autoincrement)
    b. project_id (integer, references projects.id)
    c. session_id (integer, references sessions.id)
    d. agent_id (text, references agents.agent_id)
    e. team_id (text, references teams.team_id)
    f. timestamp (datetime)
    g. context (text)
4. Create new virtual tables into the database generation script to support RAG search:
    a. A virtual table called "context_embeddings" that stores:
        i. context_id (integer, primary key, references contexts.id)
        ii. project id (integer, references projects.id)
        iii. session id (integer, references sessions.id)
        iv. agent_id (text, references agents.agent_id)
        v. team_id (text, references teams.team_id)
        vi. embedding (vector, 1536 dimensions)
    c. A virtual table called "rag_search_logs_agent" that stores:
        i. log_id (integer, primary key, autoincrement)
        ii. agent_id (text, references agents.agent_id)
        iii. query (text)
        iv. timestamp (datetime)
        v. results (text) - comma separated list of context_ids returned
    c. A virtual table called "rag_search_logs_team" that stores:
        i. log_id (integer, primary key, autoincrement)
        ii. team_id (text, references teams.team_id)
        iii. query (text)
        iv. timestamp (datetime)
        v. results (text) - comma separated list of context_ids returned
5. Whenever a connection calls the "writeDB" method, the server should also store an embedding of the context into the "context_embeddings" virtual table, using nomic-ai/nomic-embed-text-v1.5 with its search_document method.  The embedding size should be 256-dim for all interactions. The server should also store the project, session, agent_id, and team_id alongside the embedding.  
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
        sentences = ['search_document: TSNE is a dimensionality reduction algorithm created by Laurens van Der Maaten']
        embeddings = model.encode(sentences)
        print(embeddings)
6. When the server first loads, it should automatically detect if there are any contexts in the "contexts" table that do not have a corresponding embedding in the "context_embeddings" table, and if so, it should generate and store embeddings for those contexts automatically.  The 256-dim model should be used.
7. The server should also automatically delete any embeddings in the "context_embeddings" table that do not have a corresponding context in the "contexts" table.
8. The server should also automatically update any embeddings in the "context_embeddings" table if the corresponding context in the "contexts" table is updated.  This includes removing the old embedding.
9. The server should check whether the nomic-ai/nomic-embed-text-v1.5 model is available locally, and if not, it should download it automatically.  The model should be cached locally for future use.
10. The server should also create indexes on the context_ids and embedding vectors in the "context_embeddings" table for faster queries.
10. When a connection calls the "readDB" method, it should first get a count of all contexts in the database that the assigned agent has permission to see, based on the following rules:
    a. If the agent has "admin" permission level, it can see all contexts in the session the agent_id is in.
    b. If the agent has "user" permission level, it can see contexts in the same session the agent_id is in that were created by agents in the same team(s) as itself.
    c. If the agent has "guest" permission level, it can only see contexts created by itself within the same session.
11. If the count is >= 50, then the server should call a new "queryDB" method which uses the nomic-ai/nomic-embed-text-v1.5's search_query method.  This method should:
    a. Search all contexts that the agent has permission to see, based on the rules above, using a vector similarity search to find the top 20 most relevant contexts to the input query.
    d. Return these top 20 contexts to the connectio
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
        sentences = ['search_query: Who is Laurens van Der Maaten?']
        embeddings = model.encode(sentences)
        print(embeddings)
12. The queryDB method should also be available as a separate API endpoint that can be called by the GUI to test queries and see what contexts are returned for a given agent.
13. The queryDB method should also be available as a separate API endpoint that can be called by any connection as needed and see what contexts are returned for a given agent.  The queryDB method should take the following parameters:
    a. agent_id (text) - the agent ID to check permissions for
    b. query (text) - the input query to search for
    c. See all (boolean, default false) - if true, ignore permission rules and search all contexts within the same session as the agent_id in the database
14. The queryDB method should return:
    b. agent_id (text) - the agent ID that was searched for
    c. query (text) - the input query that was searched for
    d. results (list of dicts) - a list of contexts returned, each dict containing:
        i. agent_id (text)
        ii. team_id (text)
        iii. context (text)
        iv. timestamp (datetime)
    e. If there was an error, return an error message in the "details" field.
15. If the count is < 50, then the server should return all contexts that the agent has permission to see, based on the rules above.
13. Double check the codebase for any errors.
14. Test the new functionality thoroughly.
15. Update README, API docs and usage examples for new endpoints and RAG features.
16. Afterwards, commit all changes and push to the "RAG-integration" git branch