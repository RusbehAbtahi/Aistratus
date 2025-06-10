# Prompt Maker GUI – Complete User Guide

## Overview

Prompt Maker is a Windows tool for building perfect prompts for AI assistants (like ChatGPT, Claude, etc).  
It lets you fill out each aspect of your request—defining the AI’s role, the audience, how it should speak, and more.  
You never need to remember how to write the “perfect” prompt—just fill the fields, hit **Generate Prompt**, and paste the result into your AI chat!

---

## What Each Field Means

### SYSTEM
*Who the AI should be.*  
For example, “AWS Architect,” “Python Programmer (Expert),” “Project Manager,” or any expert role.  
**Tip:** Use the Role Search and role list to insert common roles.

### AUDIENCE
*Who will read the answer.*  
Examples: “junior engineer,” “yourself,” “my wife Mahsa,” “team of managers,” “recruiter.”  
The AI will tailor the explanation for this person or group.

### PURPOSE
*Why you need this response (one sentence).*  
Example: “To write a clear Lambda function,” or “To explain IAM policies for onboarding.”

### TONE
*How the answer should “sound.”*  
**Choose from:**

- **Balanced:** Neutral, well-rounded and clear; adapts to your style.
- **Analytical (Ti):** Deep, logical, step-by-step and precise—great for technical problem-solving.
- **Direct (Te/Si):** No-fluff, efficient, and to the point—best for getting quick, decisive answers.
- **Encouraging (Ne/Fe):** Supportive, positive, and motivational—boosts morale or creativity.
- **Critical-Constructive (Ti/Te/Se):** Thorough critique and actionable feedback—good for reviews or audits.
- **Visionary (Ni/Ne):** Big-picture, creative, and future-focused—explores ideas beyond the obvious.
- **Concise (Si/Te):** Short, clear summaries; delivers only essentials—perfect for checklists or fast review.
- **Empathetic (Fe/Fi):** Understanding, gentle, and emotionally tuned—ideal for stressful topics or when reassurance is needed.
- **Formal (Te/Si):** Polished and professional, like an official report or job application.

*Tip:* The words in brackets show which “cognitive functions” the tone emphasizes, but you don’t have to know MBTI to use them.

### CONFIDENCE
*How certain the AI should sound about its answer.*

- **none:** (Default) AI gives its answer without qualifying certainty.
- **low:** “I’m not sure” tone; ideas are tentative or experimental.
- **medium:** “Reasonably sure,” but open to correction; standard practice for many topics.
- **high:** Assertive and confident—use when you want strong, authoritative answers.

### RESPONSE DEPTH
*How much detail you want in the answer.*

- **none:** No special instruction; normal answer.
- **overview:** Just the basics, big picture, or summary.
- **detailed:** Step-by-step explanation, covering all main points.
- **exhaustive:** As thorough as possible, exploring all sides, edge cases, and “what ifs.”

### TASK
*What you want the AI to do. (Concrete instructions!)*  
Example: “Explain this code,” “Generate a requirements list,” or “Review my prompt and suggest improvements.”

### CONTEXT
*Background or extra info to help the AI.*  
Include facts, circumstances, or any special notes.

### CONSTRAINTS
*Rules the AI must follow.*  
Examples: “Max 200 words,” “Don’t use jargon,” “Must return a Markdown table.”

### OUTPUT FORMAT
*How the answer should be formatted.*  
Choose: “list,” “table,” “JSON,” “Markdown,” “plain English,” etc.

### REFERENCE MATERIALS
*Any files, documents, or links the AI should use.*  
Example: “See AWS_Conceptual_Map.md” or “Refer to provided CSV file.”

### EXAMPLE
*Sample input/output pairs or templates to guide the AI.*  
Show “what a good answer looks like.”

### CHECKLIST
*List of sub-tasks or requirements for the AI to tick off.*

### OUT OF SCOPE
*Anything the AI should **not** cover or discuss.*  
Example: “Do not explain Linux basics” or “Skip security considerations.”

---

## How to Use the Tool

1. **Fill in any fields you want** (leave any box blank if not needed).
2. **Use drop-downs and role search** for easy choices.
3. **Click Generate Prompt.** The tool assembles your prompt and copies it to your clipboard.
4. **Paste the prompt** into your favorite AI chat, email, or document.

---

## Special Tips

- **Clarification Option:** If you check “Ask up to 3 clarifying questions first,” the AI will clarify your needs before answering.
- **Metadata Footer:** The tool adds a line with date, model, and other details for easy reference.
- **No need to fill every box.** Only filled sections are included in the final prompt.

---

## Troubleshooting

- If you see errors, check that you’re using Python 3.x and have `tkinter` installed.
- If the window is too large, you can resize or scroll.

---

## Contact

For help, contact the developer (your husband!) or ask ChatGPT for prompt advice.

# Prompt Maker GUI – Complete User Guide

## Overview

Prompt Maker is a Windows tool for building perfect prompts for AI assistants (like ChatGPT, Claude, etc).  
It lets you fill out each aspect of your request—defining the AI’s role, the audience, how it should speak, and more.  
You never need to remember how to write the “perfect” prompt—just fill the fields, hit **Generate Prompt**, and paste the result into your AI chat!

---

## What Each Field Means

### SYSTEM
*Who the AI should be.*  
For example, “AWS Architect,” “Python Programmer (Expert),” “Project Manager,” or any expert role.  
**Tip:** Use the Role Search and role list to insert common roles.

### AUDIENCE
*Who will read the answer.*  
Examples: “junior engineer,” “yourself,” “my wife Mahsa,” “team of managers,” “recruiter.”  
The AI will tailor the explanation for this person or group.

### PURPOSE
*Why you need this response (one sentence).*  
Example: “To write a clear Lambda function,” or “To explain IAM policies for onboarding.”

### TONE
*How the answer should “sound.”*  
**Choose from:**

- **Balanced:** Neutral, well-rounded and clear; adapts to your style.
- **Analytical (Ti):** Deep, logical, step-by-step and precise—great for technical problem-solving.
- **Direct (Te/Si):** No-fluff, efficient, and to the point—best for getting quick, decisive answers.
- **Encouraging (Ne/Fe):** Supportive, positive, and motivational—boosts morale or creativity.
- **Critical-Constructive (Ti/Te/Se):** Thorough critique and actionable feedback—good for reviews or audits.
- **Visionary (Ni/Ne):** Big-picture, creative, and future-focused—explores ideas beyond the obvious.
- **Concise (Si/Te):** Short, clear summaries; delivers only essentials—perfect for checklists or fast review.
- **Empathetic (Fe/Fi):** Understanding, gentle, and emotionally tuned—ideal for stressful topics or when reassurance is needed.
- **Formal (Te/Si):** Polished and professional, like an official report or job application.

*Tip:* The words in brackets show which “cognitive functions” the tone emphasizes, but you don’t have to know MBTI to use them.

### CONFIDENCE
*How certain the AI should sound about its answer.*

- **none:** (Default) AI gives its answer without qualifying certainty.
- **low:** “I’m not sure” tone; ideas are tentative or experimental.
- **medium:** “Reasonably sure,” but open to correction; standard practice for many topics.
- **high:** Assertive and confident—use when you want strong, authoritative answers.

### RESPONSE DEPTH
*How much detail you want in the answer.*

- **none:** No special instruction; normal answer.
- **overview:** Just the basics, big picture, or summary.
- **detailed:** Step-by-step explanation, covering all main points.
- **exhaustive:** As thorough as possible, exploring all sides, edge cases, and “what ifs.”

### TASK
*What you want the AI to do. (Concrete instructions!)*  
Example: “Explain this code,” “Generate a requirements list,” or “Review my prompt and suggest improvements.”

### CONTEXT
*Background or extra info to help the AI.*  
Include facts, circumstances, or any special notes.

### CONSTRAINTS
*Rules the AI must follow.*  
Examples: “Max 200 words,” “Don’t use jargon,” “Must return a Markdown table.”

### OUTPUT FORMAT
*How the answer should be formatted.*  
Choose: “list,” “table,” “JSON,” “Markdown,” “plain English,” etc.

### REFERENCE MATERIALS
*Any files, documents, or links the AI should use.*  
Example: “See AWS_Conceptual_Map.md” or “Refer to provided CSV file.”

### EXAMPLE
*Sample input/output pairs or templates to guide the AI.*  
Show “what a good answer looks like.”

### CHECKLIST
*List of sub-tasks or requirements for the AI to tick off.*

### OUT OF SCOPE
*Anything the AI should **not** cover or discuss.*  
Example: “Do not explain Linux basics” or “Skip security considerations.”

---

## How to Use the Tool

1. **Fill in any fields you want** (leave any box blank if not needed).
2. **Use drop-downs and role search** for easy choices.
3. **Click Generate Prompt.** The tool assembles your prompt and copies it to your clipboard.
4. **Paste the prompt** into your favorite AI chat, email, or document.

---

## Special Tips

- **Clarification Option:** If you check “Ask up to 3 clarifying questions first,” the AI will clarify your needs before answering.
- **Metadata Footer:** The tool adds a line with date, model, and other details for easy reference.
- **No need to fill every box.** Only filled sections are included in the final prompt.

---

## Troubleshooting

- If you see errors, check that you’re using Python 3.x and have `tkinter` installed.
- If the window is too large, you can resize or scroll.

---

## Contact

For help, contact the developer (your husband!) or ask ChatGPT for prompt advice.

