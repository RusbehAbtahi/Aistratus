**Epic Goal**

Deliver a cross-platform Tkinter desktop application that lets the user  
• type a prompt,  
• send it to the backend,  
• see the running cost in real time, and  
• hard-stop the GPU instance.

This epic groups every user-facing GUI feature defined in **RQL §1 (Desktop GUI)**.

**Why it matters**

The GUI is the single entry-point for humans. Even a shell-only MVP (without live backend)
forces us to define request/response contracts early and gives visual progress to the PO.

**Acceptance for epic closure**

– All child stories are *Done* (GUI-001 … GUI-006).  
– Demo on Windows & macOS shows: prompt-send → inference result → cost tick.  
– PO signs off on UX flow, cost transparency, and emergency Stop GPU UX.
