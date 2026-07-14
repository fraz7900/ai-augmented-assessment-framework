Literature Review — AI-Assisted Assessment & Evaluation Methodologies

*Prepared by: Jennifer  |  Project: AI-Augmented Assessment Framework  |  Date: July 13, 2026*

This document reviews academic and industry resources connected to our assessment process, ahead of resubmitting the work plan. It covers three areas directly tied to our team's responsibilities: (1) LLM-based compliance/policy assessment, (2) RAG retrieval-and-generation evaluation metrics, and (3) confidence/uncertainty and hallucination detection for AI outputs.

# **1\. LLM-Based Compliance & Framework-Mapping Assessment**

## **PROPARAG: An Automated Framework for Cybersecurity Policy Compliance Assessment Against Security Control Standards**

*Saha & Shukla (2026), arXiv preprint*

* Presents an audit-support tool that automatically evaluates organizational cybersecurity policies against security controls: for each control, it retrieves relevant policy evidence, scores coverage, flags missing elements, and generates an explanation and recommendation.  
* Evaluated on 1,007 NIST SP 800-53 controls across two real-world organizational policy corpora using multiple LLMs; reported F1 scores of 88.54 and 82.31 on the two corpora.  
* Directly relevant: this is close to our own "evidence coverage / gap identification / AI-generated suggestion" workflow, and offers a concrete benchmark methodology (per-control F1) we could adapt for our own scoring validation.

**Source:** [https://arxiv.org/pdf/2605.07515](https://arxiv.org/pdf/2605.07515)

## **Towards the Development of an LLM-Based Methodology for Automated Security Profiling in Compliance with Ukrainian Cybersecurity Regulations**

*Shafranskyi, Stopochkina & Ilin (2026), arXiv preprint*

* Proposes a Retrieval-Augmented Generation (RAG) advisor that ingests a vector database of national regulations and organizational policies to automate generation of a target security profile, referencing ISO/IEC 27001 and NIST CSF.  
* Frames the goal as reducing manual complexity and human error while keeping technical controls traceable to legal/regulatory requirements, the same traceability goal as our "evidence, gaps, and assumptions" dashboard view.  
* Useful as a reference architecture for combining a document vector store with framework-specific prompting, similar to what Zhiyao/Andy are scoping for our ingestion pipeline.

**Source:** [https://arxiv.org/pdf/2604.06274](https://arxiv.org/pdf/2604.06274)

## **AI-Powered Cybersecurity Framework Mappings (industry methodology writeup, CyberStrong/CyberSaint)**

*CyberSaint, industry publication*

* Describes a commercial approach to automated framework crosswalking (e.g., control-to-control mapping across standards) using embeddings plus semantic similarity, combined with LLM review, and a feedback loop where user corrections improve mapping accuracy over time.  
* Relevant as a practical, non-academic example of how vendors currently handle the exact C2M2 ↔ NIST CSF mapping problem in our project scope, including how they keep a human-in-the-loop correction step.

**Source:** [https://www.cybersaint.io/blog/ai-powered-cybersecurity-framework-mappings-automating-compliance-with-cyberstrong](https://www.cybersaint.io/blog/ai-powered-cybersecurity-framework-mappings-automating-compliance-with-cyberstrong)

# **2\. RAG Retrieval & Generation Evaluation Metrics**

## **Retrieval-Augmented Generation for Natural Language Processing: A Survey**

*Survey paper, arXiv (2607.13193)*

* Provides a taxonomy of RAG evaluation metrics organized by focus: retrieval quality (Precision@k, Recall@k, Hit Rate, MRR, NDCG), generation quality (faithfulness, answer correctness), and system-level robustness.  
* Notably distinguishes answer faithfulness from answer correctness — an answer can be faithful to a retrieved context that is itself wrong, which is an important caveat for our confidence scoring design.  
* Good primary reference for defining our own metric taxonomy (retrieval recall@k plus answer faithfulness, as scoped in Andy's role).

**Source:** [https://arxiv.org/pdf/2407.13193](https://arxiv.org/pdf/2407.13193)

## **RAGalyst: Automated Human-Aligned Agentic Evaluation for Domain-Specific RAG**

*arXiv preprint (2511.04502)*

* Formalizes Recall@K (a.k.a. Hit Rate@K): the proportion of queries for which the ground-truth supporting context appears within the top-k retrieved results — the exact metric named in Andy's evaluation-harness responsibility.  
* Emphasizes building a human-aligned golden dataset for domain-specific evaluation, which maps onto our own need for "golden and adversarial regression cases" against NIST CSF / C2M2 evidence.

**Source:** [https://arxiv.org/pdf/2511.04502](https://arxiv.org/pdf/2511.04502)

## **A Survey on Knowledge-Oriented Retrieval-Augmented Generation**

*arXiv preprint (2503.10677)*

* Summarizes established RAG evaluation frameworks (RAGAS, ARES, TruLens, KILT) and their core metrics: context relevance, R-precision, Recall@k, and Answer Faithfulness/Groundedness (breaking an answer into individual claims and verifying each against retrieved context).  
* The claim-level groundedness check described here is a strong candidate methodology for our own "AI-generated suggestions tied to evidence" traceability requirement.

**Source:** [https://arxiv.org/pdf/2503.10677](https://arxiv.org/pdf/2503.10677)

## **RAG Evaluation Metrics in 2026: Faithfulness & More**

*FutureAGI, industry publication*

* Practical warning relevant to our design: faithfulness scores can stay high even when context recall is low, because a model can still answer fluently from an incomplete evidence set — meaning faithfulness alone would not catch a case where our tool missed a relevant document.  
* Recommends tracking context recall and faithfulness as separate, complementary metrics rather than a single blended score.

**Source:** [https://futureagi.com/blog/rag-evaluation-metrics-2025/](https://futureagi.com/blog/rag-evaluation-metrics-2025/)

# **3\. Confidence, Uncertainty, and Hallucination Detection**

## **Uncertainty Quantification and Confidence Calibration in Large Language Models: A Survey**

*Survey paper, arXiv (2503.15850)*

* Surveys methods for estimating how confident an LLM should be in its own output, distinguishing model confidence from true uncertainty, and covering both white-box signals (token probabilities, entropy) and black-box signals (multi-sample consistency, semantic grouping).  
* Directly informs the "AI evaluation metrics for evidence quality, confidence, and consistency" task on our work plan — gives us named, citable methods rather than an ad-hoc confidence score.

**Source:** [https://arxiv.org/html/2503.15850](https://arxiv.org/html/2503.15850)

## **Uncertainty Quantification for Hallucination Detection in Large Language Models: Foundations, Methodology, and Future Directions**

*arXiv preprint (2510.12040)*

* Explains that LLMs tend to produce plausible-but-false answers specifically when uncertain, rather than declining to answer — reinforcing why our tool needs an explicit confidence/flagging layer rather than trusting fluency as a proxy for correctness.  
* Describes the common practical pattern of setting a threshold on an uncertainty score to trigger a binary "flag for human review" decision, which maps well onto the sanitized/human-reviewed report step in our workflow.

**Source:** [https://arxiv.org/pdf/2510.12040](https://arxiv.org/pdf/2510.12040)

## **Confidence Calibration in LLMs (topic overview)**

*Emergent Mind, research summary*

* Describes fact-level ("atomic") calibration, which pinpoints which specific claims in a longer answer are likely hallucinated, rather than scoring the whole answer as one unit.  
* Also describes calibration-aware escalation, i.e., routing only low-confidence outputs to human override — a lightweight pattern we could apply to keep human review focused on the assessment items our tool is least sure about.

**Source:** [https://www.emergentmind.com/topics/confidence-calibration-in-llms](https://www.emergentmind.com/topics/confidence-calibration-in-llms)

# **Summary & Recommendations**

• Adopt separate, named metrics rather than one blended "confidence" score: retrieval-side (Recall@k / context recall) and generation-side (answer faithfulness / groundedness), following the RAGAS/ARES/TruLens convention.

• Consider claim-level (atomic) grounding checks for AI-generated suggestions, so each recommendation in the dashboard can show which specific evidence sentence(s) support it — improving auditability for the anonymized report.

• Build a small "golden \+ adversarial" evaluation set of NIST CSF / C2M2 questions early, since every metric above (F1, Recall@k, faithfulness) requires labeled test cases to be meaningful.

• The PROPARAG paper's per-control F1 evaluation on NIST SP 800-53 is the closest existing benchmark to our exact use case and is worth a deeper read by Jennifer and Andy before finalizing the evaluation harness design.

• Low confidence/uncertainty should route to explicit human review flags in the dashboard, not be silently absorbed into a single score, per the calibration-aware escalation pattern.