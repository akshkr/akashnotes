## Interview Study Plan: Agentic AI & LLMs
---

### Ⅰ. Foundational LLM Concepts 🧠

* **Transformer Architecture:** Understand the core components (self-attention, multi-head attention, feed-forward networks, positional encodings). Be ready to discuss *why* it's effective for language tasks.
* **LLM Training & Fine-tuning:**
    * Pre-training objectives (e.g., Masked Language Modeling, Next Token Prediction).
    * Fine-tuning strategies (full fine-tuning, PEFT techniques like LoRA, QLoRA). When and why would you choose one over the other?
    * Reinforcement Learning from Human Feedback (RLHF): Core concepts and its importance in aligning LLMs.
* **Prompt Engineering:**
    * Different prompting techniques (zero-shot, few-shot, chain-of-thought, tree-of-thought).
    * How prompts influence agent behavior and task execution.
* **Embeddings:** How text is converted to vector representations and their significance in semantic search and context retrieval (critical for your knowledge graph).
* **Evaluation Metrics for LLMs:**
    * Task-specific metrics (e.g., ROUGE for summarization, BLEU for translation).
    * Understanding perplexity.
    * How you evaluated the LLM performance within your agentic system.
* **Bias, Ethics, and Limitations of LLMs:** Be prepared to discuss potential issues and mitigation strategies.

---

### Ⅱ. Agentic AI & Workflow Design ⚙️

This is central to your project.

* **Core Concepts of Agentic AI:**
    * Definition of an AI agent (autonomy, goal-orientation, perception, action).
    * Key components of an agent: LLM as the "brain," planning module, memory (short-term, long-term), tool usage.
    * Differences between single-agent and multi-agent systems.
* **Agentic Workflow Framework (Your Design):**
    * **HLD & LLD:** Be ready to draw and explain your architecture. Justify your design choices.
        * What were the key modules/services?
        * How did they interact? Data flow.
        * What were the trade-offs you considered? (e.g., scalability, latency, complexity).
        * How did you ensure modularity and extensibility for adoption by other teams?
    * **Decision-Making & Planning:** How does your agent decide what to do next? (e.g., ReAct framework, LLM-based planning).
    * **Tool Usage/Function Calling:** How did your agent interact with external tools or APIs (like New Relic)?
    * **State Management & Memory:** How did the agent maintain context and learn from interactions within a workflow?
    * **Error Handling & Resilience:** How did your workflow handle failures or unexpected outputs from the LLM or tools?
* **Evaluation of Agentic Frameworks (CrewAI & AutoGen):**
    * Your specific evaluation criteria (e.g., ease of use, scalability, flexibility, community support, specific features relevant to your project).
    * Key strengths and weaknesses you identified for CrewAI and AutoGen.
    * How did this evaluation influence your own framework design? What did you adopt, adapt, or decide against?
* **Orchestration:** How were tasks and agents coordinated within your framework?
* **Monitoring & Observability:** How did you track the agent's behavior, performance, and debug issues? (e.g., tracing, logging).

---

### Ⅲ. Knowledge Graphs (KG) & Context Awareness 🕸️

Your KG for New Relic entities is a key differentiator.

* **Knowledge Graph Fundamentals:**
    * What is a KG? (Nodes, edges, properties, ontologies/schemas).
    * Why use a KG over other data storage/retrieval methods for context?
    * How KGs enhance LLM context and reasoning.
* **Your New Relic KG:**
    * **Design & Schema:** How did you define the entities and relationships for New Relic? What was your ontology?
    * **Construction:** How was the KG built and populated? (Data sources, extraction methods, updates).
    * **Integration with Agentic Workflow:**
        * How did the agent query the KG? (e.g., SPARQL, graph-specific query languages, LLM generating queries).
        * How was information from the KG used to provide context to the LLM/agent? (e.g., augmenting prompts, providing relevant entity information).
        * Specific examples of how KG context improved the agent's performance or decision-making in incident management.
    * **Challenges:** What challenges did you face in building and using the KG? (e.g., data quality, scalability, keeping it up-to-date).
* **Retrieval Augmented Generation (RAG) vs. KG:** Be prepared to discuss the relationship. Your KG likely served as a sophisticated knowledge source for a RAG-like pattern.

---

### Ⅳ. Incident Management Agent & Root Cause Analysis (RCA) 🛠️🔥

This is your primary application.

* **Incident Management Lifecycle:** Basic understanding of detection, logging, diagnosis, resolution, and post-mortem.
* **Your Incident Management Agent:**
    * **Specific Tasks:** What exact incident management tasks did the agent automate or accelerate?
    * **Workflow:** Describe the step-by-step process the agent followed for a typical incident.
    * **Inputs & Outputs:** What triggered the agent? What information did it consume? What were its outputs/actions?
    * **Interaction with SREs:** How did SREs interact with the agent? Was there a human-in-the-loop component?
* **Automated Root Cause Analysis (RCA):**
    * **Methodology:** How did your agent approach RCA? (e.g., analyzing logs, metrics, traces, KG data, correlating events).
    * **Role of LLM & KG:** How did the LLM reason about potential causes? How did the KG provide critical context about dependencies and system states for RCA?
    * **Examples:** Be ready with specific examples of how the agent identified root causes.
    * **Accuracy & Limitations:** How accurate was the automated RCA? What were its limitations?
    * **Metrics:** How did you measure the success/impact of the agent? (e.g., MTTR reduction, improved SRE efficiency).
* **Integration with New Relic:** Deep dive into how the agent leveraged New Relic data (via KG or direct APIs) for its tasks.

---

### Ⅴ. System Design & Architecture Questions 🏗️

Based on your "designed the core architecture" claim.

* **Scalability:** How would your agentic platform scale to handle more users, more agents, or more complex workflows?
* **Reliability & Fault Tolerance:** What happens if parts of your system fail (e.g., LLM API down, KG unresponsive)?
* **Security:** How did you address security considerations, especially if dealing with sensitive incident data or interacting with production systems?
* **Cost Optimization:** Considerations for LLM API costs, compute resources, etc.
* **Data Flow & Communication:** Be able to clearly articulate how data moves through your system.
* **Modularity & Reusability:** How did your design facilitate reuse of components for different agents or workflows?

---

### Ⅵ. Behavioral & Project-Specific Questions 🤔

* **"Tell me about your project..."**: Have a crisp, engaging summary.
* **Challenges Faced:** What were the biggest technical or non-technical challenges you encountered, and how did you overcome them?
* **What would you do differently?**: Reflect on potential improvements or alternative approaches.
* **Impact of the project:** Quantify the benefits if possible.
* **Collaboration:** How did you collaborate with internal/external teams?
* **Why these frameworks (CrewAI/AutoGen)?** Deep dive into your reasoning for evaluating them.
* **Why an agentic approach?** Justify why agents were the right solution for incident management.

---

### Study Tips:

* **Revisit Your Code/Designs:** Refresh your memory on the specifics of what you built.
* **Whiteboard Practice:** Practice explaining your HLD, LLD, and workflows on a whiteboard or virtually.
* **Mock Interviews:** Practice with peers or mentors, focusing on these topics.
* **Stay Updated:** The field is evolving rapidly. Be aware of recent advancements in LLMs and agentic AI, even if they weren't part of your project.
* **Prepare Questions for the Interviewer:** Show your engagement and continued interest in the field.
