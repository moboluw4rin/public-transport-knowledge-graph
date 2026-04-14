# Ontology Modeling: Bi-Chat Orchestration Report

## Methodology Overview
This project employs a **sequential two-chat orchestration** methodology to extend existing ontologies and address specific Competency Questions (CQs). By decoupling design from execution, we maintain high logical consistency and clean code generation.

* **Chat A - The Orchestrator**: Acts as the strategic lead. It handles research, evaluates outputs from the builder, and performs "Prompt Engineering" to create high-fidelity instructions.
* **Chat B - The Builder**: Acts as the technical executor. It receives refined prompts from the Orchestrator to perform script generation and RDF construction without the "noise" of the brainstorming phase.


## Phase 1: Mapping and Prompt Creation
**Goal:** Identify logical mappings between domain requirements and the existing ontology schema.

### 1a. Orchestrator - Prompt Creation
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    Create a prompt based on the following framework which will be utilised by a different chat. 
    ```
    # Senario:
    I am creating an ontology of the London underground. 

    # Inputs:
    - 2 Existing Otologies
    - 10 Competency Questions

    # Task
    takes 2 existing ontologies which i give you, and uses the set of 10 CQs.

    Take the 10 CQs and extract classes, relations and properties from it. 

    Then map it to the 2 ontologies and try to use existing classes and as much as possible  but ensure each existing ontology is extended by at least 2 sub classes and sub properties each. 

    Lastly from those extracted classes and relations create 10 more CQs which will later be translated into SPARQL queries. 

    # GOAL 
    The goal is to extract the classes and relations from the CQs and generate 10 more CQs

    # OUTPUT
    - a mapping of Classes, relations and properties from the CQs which i need to have in order to extend the imported ontologies
    - 10 new CQs
    ```
    ```

</details>

### 1b. Builder - Ontology Mapping Execution
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    # Scenario

    I am designing an ontology for the London Underground system.

    # Inputs 

    ##Two existing ontologies (with prefixes and key classes)
    - (Transmodel):  https://oeg-upm.github.io/snap-docs/
    -  (Owl-Time): https://www.w3.org/TR/owl-time/

    ##A list of 10 competency questions (CQs)
    1. Which public transport stations are officially designated as fully wheelchair accessible?
    2. What is the total operational length, in miles, of the Circle Line?
    3. Which transport disruptions are currently affecting the Piccadilly Line?
    4. What is the exact delay duration (in minutes) caused by the signal failure at Victoria Station?
    5. Which stations serve as interchange points between the District Line and Bakerloo Line?
    6. What is the reported severity level (e.g., Minor, Severe, Suspended) of the incident at King's Cross St. Pancras?
    7. Which transport routes were inaugurated before the year 1989?
    8. What is the alternative bus replacement route provided for Caledonian Road Station during its closure?
    9. Which maintenance events are scheduled to occur between September and December?
    10. What is the standard passenger capacity of the rolling stock used on the Victoria Line?# Task

    You must perform THREE steps:

    ## Step 1 — Extract ontology elements from CQs

    For each of the 10 competency questions:

    * Identify candidate **classes**
    * Identify **object properties (relations between classes)**
    * Identify **datatype properties (attributes like names, IDs, numbers, etc.)**

    Output this in a structured table.

    ---

    ## Step 2 — Map to existing ontologies (TBox mapping)

    Using the two provided ontologies:

    * Reuse existing classes and properties wherever possible
    * Create **new classes only when necessary**
    * Map my classes to existing ones using:

    * `rdfs:subClassOf`
    * `rdfs:subPropertyOf`

    ### Requirements:

    * Each ontology MUST be extended with:

    * At least **2 subclass mappings**
    * At least **2 subproperty mappings**
    * Clearly show:

    * which ontology each mapping belongs to
    * why the mapping is appropriate

    ---

    ## Step 3 — Generate 10 additional competency questions

    Using:

    * the original 10 CQs
    * the extracted classes and properties

    Generate 10 NEW competency questions that:

    * are NOT duplicates
    * are relevant to the domain (London Underground)
    * use the same ontology concepts
    * increase coverage of the domain

    ---

    # Output Format

    ## 1. Extracted Ontology Elements (Table)

    | CQ | Classes | Object Properties | Datatype Properties |
    | -- | ------- | ----------------- | ------------------- |

    ---

    ## 2. TBox Mapping

    ### Class Mappings

    * MyClass → ExternalClass (ontology name)
    Explanation: ...

    ### Property Mappings

    * MyProperty → ExternalProperty (ontology name)
    Explanation: ...

    ---

    ## 3. Final Ontology Terms

    ### Classes

    * list of final classes

    ### Object Properties

    * list of relations

    ### Datatype Properties

    * list of attributes

    ---

    ## 4. 10 New Competency Questions

    1. ...
    2. ...
    ...
    3. ...

    ---

    # Constraints

    * Prefer reuse over creating new classes
    * Keep ontology simple and consistent
    * Use clear, domain-relevant naming
    * Ensure mappings are logically valid

    # Goal

    To produce a clean ontology design foundation that:

    * aligns with the competency questions
    * extends two existing ontologies
    * can later be implemented in Turtle and queried with SPARQL
    ```

</details>



## Phase 2: Ontology Creation & Continuation
**Goal:** Develop the core Python scripts required to programmatically generate the expanded ontology.

### 2a. Orchestrator - Continuation Script Design
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    This is the response from the builder:

    ```
    “Insert Response here”
    ```

    Generate a prompt to task the builder to utilise the its previous response to generate the ontology_builder using rdflib.
    ```


</details>

### 2b. Builder - Ontology Creation
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    # Continuation Task — Ontology Implementation

    You have already:

    * Extracted classes, object properties, and datatype properties from the 10 competency questions
    * Created TBox mappings to two external ontologies (Transmodel + OWL-Time)
    * Defined the final ontology terms (classes, properties, mappings)

    Now, use THAT previous output to generate a Python rdflib script that constructs the ontology (TBox only).

    ---

    ## Task

    Generate a clean, runnable Python script using rdflib that:

    ### 1. Creates the Graph

    * Initialize an rdflib Graph
    * Define namespaces:

    * My ontology: http://example.org/ontology-express#
    * Transmodel (tmfac, tmorg, etc.)
    * OWL-Time (time)
    * RDF, RDFS, OWL, XSD

    ---

    ### 2. Defines the Ontology

    * Declare the ontology as `owl:Ontology`
    * Add `owl:imports` for:

    * Transmodel modules already used
    * OWL-Time ontology

    ---

    ### 3. Adds Classes

    For ALL previously defined classes:

    * Add `(class, rdf:type, owl:Class)`
    * Add `rdfs:label`

    ---

    ### 4. Adds Subclass Mappings

    * Implement ALL `rdfs:subClassOf` relationships from the previous output
    * Use correct external IRIs (Transmodel + OWL-Time)

    ---

    ### 5. Adds Object Properties

    For ALL object properties:

    * Add `(property, rdf:type, owl:ObjectProperty)`
    * Add `rdfs:label`

    ---

    ### 6. Adds Datatype Properties

    For ALL datatype properties:

    * Add `(property, rdf:type, owl:DatatypeProperty)`
    * Add `rdfs:label`

    ---

    ### 7. Adds Subproperty Mappings

    * Implement ALL `rdfs:subPropertyOf` relationships

    ---

    ### 8. Output

    * Serialize the graph to a file called `tfl_ontology.ttl`
    * Use Turtle format

    ---

    ## Constraints

    * ONLY use the ontology elements already defined earlier in this chat
    * DO NOT invent new classes or properties
    * DO NOT include individuals (ABox)
    * Keep code clean and readable
    * Use consistent naming via rdflib Namespace (e.g., EX.UndergroundStation)

    ---

    ## Output Format

    Return:

    1. Full Python rdflib script
    2. Short explanation of how to run it
    ```


</details>


## Phase 3: Verification and Correction (1)
**Goal:** Validate the generated ontology against CQs and fix logical inconsistencies or syntax errors.

### 3a. Orchestrator - Ontology Verifier
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    I have attached the generated script and the .ttl which it generated. Evaluate it and give another prompt if there is correct required.

    ```
    ontology_builder_initial.py (Script provided by builder chat)
    ontology_initial .ttl file from that script. (file produced by ontology_builder)
    ```
    ```

</details>

### 3b. Builder - Ontology Correction
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    Review the rdflib ontology script you just generated and produce a corrected version.

    Use the same ontology design as before, but now do the following:

    1. Validate and correct all namespace IRIs and ontology imports for Transmodel and OWL-Time.
    2. Check whether each subclass mapping and subproperty mapping is semantically valid.
    3. Add missing `rdfs:subClassOf` mappings for local classes that should extend existing transport classes, especially `UndergroundLine` and `UndergroundRoute`.
    4. Remove or simplify any classes or properties that are not necessary for answering the 20 competency questions.
    5. Keep this as a TBox-only ontology generator in rdflib.
    6. Output:

    * the corrected full Python script
    * a short bullet list of what was fixed and why

    Constraints:

    * Do not add individuals.
    * Do not invent brand-new modelling areas outside the existing CQ scope.
    * Keep the ontology practical for later population from data sources.
    ```
</details>

## Phase 4: Verification and Correction (2) 
**Goal:** Ensure alignment with external ontologies and competency questions

### 4a. Orchestrator - Cleanup Strategy
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    Verify the fixed ontology_builder.py and its declared classes, properties and relationships are valid. 
    ```
    ontology_builder.py	(updated version)
    base_ontology.ttl (produced by updated script)
    ```

    Then provide me with a prompt, which identifies the issues and how to fix them.
    ```

</details>

### 4b. Builder - Technical Cleanup Execution
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    # Continuation Task — Fix Ontology Builder (v2)

    You previously generated a Python rdflib script (`ontology_builder_v2.py`) that builds a TBox ontology for the London Underground.

    Now, update THAT script to fix specific semantic and modelling issues while keeping the overall ontology design unchanged.

    ---

    ## Task

    Modify the existing script so that the ontology it generates is:

    * semantically correct
    * consistent with the competency questions
    * properly aligned with Transmodel and OWL-Time

    ---

    ## Required Fixes

    ### 1. Fix incorrect subproperty mapping

    The current mapping:

    * `lineHasRoute rdfs:subPropertyOf tmj:onLine`

    is likely directionally incorrect.

    You must:

    * either REMOVE this mapping
    OR
    * replace it with a correctly aligned property:

    * e.g. `routeOnLine` (Route → Line)
    * with appropriate domain and range

    Do NOT keep a semantically incorrect mapping.

    ---

    ### 2. Fix `hasDelayDuration`

    Currently:

    * it is defined as an **object property**
    * but mapped to `time:hasXSDDuration`

    This is inconsistent.

    You must:

    * either convert `hasDelayDuration` into a **datatype property** with range `xsd:duration`
    OR
    * remove it entirely and rely on `delayMinutes`

    Choose the simpler and more consistent option.

    ---

    ### 3. Validate all subclass mappings

    Check that all `rdfs:subClassOf` mappings:

    * are logically valid
    * correctly reference Transmodel or OWL-Time classes

    Keep valid mappings such as:

    * `UndergroundStation ⊑ tmfac:StopPlace`
    * `UndergroundLine ⊑ tmj:Line`
    * `UndergroundRoute ⊑ tmj:Route`
    * `RollingStockType ⊑ tmfac:VehicleType`

    ---

    ### 4. Validate all subproperty mappings

    Check that:

    * domain and range of each local property align with the external property
    * no direction mismatches exist
    * no incorrect ontology terms are referenced

    Remove any unsafe mappings.

    ---

    ### 5. Keep scope aligned with competency questions

    * Do NOT add new classes or properties
    * Do NOT expand the ontology beyond the CQ scope
    * Keep the ontology minimal and usable for population

    ---

    ## Constraints

    * Do NOT include individuals (ABox)
    * Keep the ontology as a TBox-only generator
    * Keep naming consistent (`EX.*`)
    * Preserve working structure of the script
    * Only fix errors — do not redesign the ontology

    ---

    ## Output

    Return:

    1. The corrected full Python rdflib script
    2. A short bullet list of what was fixed and why
    ```


</details>

### 4c. Additional 10 CQs
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    You are an expert in machine learning. Given this London Underground ontology and the existing set of competency questions, generate 10 additional competency questions that complement and help validate the existing ones. Where possible, the questions should be answerable using the current ontology structure. If a question reveals a gap or requires extending the ontology, note what additions would be needed.
    ```

</details>

## Phase 5: Documentation Cleanup
**Goal:** Finalize the knowledge engineering documentation and ensure all scripts and TTL files are formatted.

### 5a. Orchestrator - Documentation Structuring
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    Provide me with a prompt which allows the generation chat to include labels and comments for every class, property and relationship it defined. It shouldn't change any logic or relation but just add the metadata such as comments. 
    ```

</details>

### 5b. Builder - Document Generation
<details>
<summary>Click to view Prompt</summary>

    ```markdown
    You already generated the current ontology builder Python script and its Turtle output for my London Underground TBox ontology.

    Update the existing generation script only.

    Task:
    Modify the current `ontology_builder.py` so that every ontology element it creates includes human-readable documentation metadata, while keeping the ontology logic exactly the same.

    Requirements:

    1. Do not change any ontology logic, modelling, mappings, hierarchy, imports, domains, ranges, or serialization behaviour.
    2. Do not add or remove classes, properties, or mappings.
    3. Only enhance documentation for existing ontology elements.

    For every class created by the script, add:

    * `rdfs:label`
    * `rdfs:comment`

    For every object property created by the script, add:

    * `rdfs:label`
    * `rdfs:comment`

    For every datatype property created by the script, add:

    * `rdfs:label`
    * `rdfs:comment`

    For the ontology itself, add:

    * `rdfs:label`
    * `rdfs:comment`

    Comment-writing rules:

    * Comments must be concise, domain-relevant, and specific to the London Underground ontology.
    * Comments must explain the role of the class/property in the ontology.
    * Do not write vague comments like “A class in the ontology.”
    * Keep naming and terminology consistent with the competency questions and existing ontology scope.

    Implementation rules:

    * Reuse the existing helper-function style if possible.
    * Update helper functions if needed so comments are added cleanly.
    * Preserve the current namespace structure and file output.
    * Keep the script runnable as-is.

    Output:

    1. Return the full updated Python script
    2. Then briefly list what documentation metadata was added

    Important:

    * This is a documentation-only update.
    * Do not alter any semantics or graph structure beyond adding labels/comments.
    ```
</details>