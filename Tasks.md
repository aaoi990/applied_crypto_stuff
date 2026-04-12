# Inclusive Task Sheet

## Development Work & Problem Solving

*A Structured Framework for Starting, Progressing and Completing Tasks*

---

> **Purpose:** This task sheet provides a clear, repeatable structure for approaching development work and problem solving. It is designed for all team members and supports different working styles, thinking preferences and communication needs. Use it as a guide, not a rigid rule. Adapt it to suit the way you work best.

---

## Task Information

| Field               | Value                                              |
|---------------------|-----------------------------------------------------|
| **Task Name**       |                                                     |
| **Assigned To**     |                                                     |
| **Date Started**    |                                                     |
| **Target Completion** |                                                   |
| **Priority**        | High / Medium / Low                                 |
| **Complexity**      | Simple / Moderate / Complex                         |
| **Status**          | Not Started / In Progress / Blocked / Review / Done |

---

## Phase 1 â€“ Understand the Task

Before writing any code, take time to fully understand what is being asked. This is the most important phase. Spending time here prevents rework later.

### 1.1 What is the goal?

Write a single, clear sentence describing the purpose of this task. Focus on what it achieves, not how to build it.

> *Example: "Allow users to reset their password via email so they can regain access to their account."*

**Goal:**


### 1.2 Acceptance criteria

List the specific, measurable conditions that must be true for this task to be considered complete. If these were not provided, ask for them before starting.

- [ ] Criterion 1:
- [ ] Criterion 2:
- [ ] Criterion 3:
- [ ] Criterion 4:

### 1.3 Clarification checklist

Work through these questions. If you cannot answer any of them clearly, that is your signal to ask before starting.

- [ ] I can explain the task in my own words
- [ ] I know who the end user or consumer of this work is
- [ ] I know which systems, services, or files are affected
- [ ] I know what inputs the code will receive
- [ ] I know what outputs or side-effects are expected
- [ ] I understand the edge cases and error scenarios
- [ ] I know where to find related documentation or prior work
- [ ] I know who to contact if I have questions

> ðŸ’¡ **Asking questions is a strength:** Clarifying requirements early saves time and improves quality. Write your questions in a message or document before raising them. This gives you time to organise your thoughts and gives the other person clear information to respond to.

---

## Phase 2 â€“ Plan Your Approach

Planning reduces overwhelm and makes complex work manageable. You do not need to plan every detail, but you do need a clear starting point and a sequence of steps.

### 2.1 Break it down

Divide the task into small, concrete sub-tasks. Each sub-task should be something you can complete in roughly 30 minutes to 2 hours. If a sub-task feels too large, break it down further.

| # | Sub-Task Description | Est. Time | Status |
|---|----------------------|-----------|--------|
| 1 |                      |           |        |
| 2 |                      |           |        |
| 3 |                      |           |        |
| 4 |                      |           |        |
| 5 |                      |           |        |
| 6 |                      |           |        |
| 7 |                      |           |        |
| 8 |                      |           |        |

### 2.2 Identify what you need

- [ ] Access to required systems, repos, or environments
- [ ] Relevant documentation, API specs, or design files
- [ ] Test data or example inputs and outputs
- [ ] Dependencies on other people's work (note who and what)
- [ ] Any credentials, permissions, or configuration

### 2.3 Choose your starting point

Identify the single smallest action you can take right now. This is your entry point. It does not need to be the most important part. It just needs to be clear and achievable.

> *Example: "Create a new branch and add an empty test file for the password reset endpoint."*

**My starting point:**


> ðŸ’¡ **If you cannot choose a starting point:** Pick the sub-task that has the fewest unknowns. Alternatively, start with writing a test for the expected behaviour, or create the file and folder structure. Movement creates momentum.

---

## Phase 3 â€“ Do the Work

Work through your sub-tasks in order. Focus on one sub-task at a time. You do not need to hold the entire solution in your head.

### 3.1 Working rhythm

- Work in focused blocks of 25â€“50 minutes with short breaks.
- After each block, note what you completed and what comes next.
- Commit your code regularly with clear, descriptive commit messages.
- If you finish a sub-task, mark it as done in your plan and move to the next one.

### 3.2 While you work, record your decisions

Use this space to note decisions, assumptions, and reasoning as you go. This is valuable both for your own reference and for code reviews.

| Date / Time | Decision or Assumption | Reasoning |
|-------------|------------------------|-----------|
|             |                        |           |
|             |                        |           |
|             |                        |           |
|             |                        |           |
|             |                        |           |

---

## Phase 4 â€“ Getting Unstuck

Getting stuck is a normal part of development. It is not a failure. This section gives you a structured approach to move forward when progress stalls.

### 4.1 The 15-Minute Rule

When you hit a block, try to resolve it independently for 15 minutes. Set a timer. After 15 minutes, if you have not made progress, move to 4.2.

### 4.2 Diagnose the block

Identify which type of block you are experiencing. Tick the one that best describes your situation.

- [ ] I do not understand the requirement â†’ go back to Phase 1
- [ ] I understand the requirement but do not know how to implement it
- [ ] I know how to implement it but my code is not working as expected
- [ ] I am overwhelmed by the size or complexity of the task
- [ ] I am blocked by something outside my control (access, another person's work, environment)
- [ ] I am struggling to focus or feel overloaded

### 4.3 Structured problem-solving steps

#### If you don't know how to implement it

- Search for examples in the existing codebase using grep, IDE search, or code navigation.
- Read the official documentation for the library, framework, or API.
- Search for a specific, focused question (avoid broad searches).
- Sketch a rough approach in comments or pseudocode before writing real code.
- If still stuck after 15 minutes of research, prepare a written summary and ask a colleague.

#### If your code is not working

- Read the full error message. Copy it somewhere visible.
- Identify which line of code is causing the error.
- Add logging or print statements around the problem area.
- Simplify: strip the code back to the smallest version that reproduces the issue.
- Check your assumptions: are the inputs what you expect them to be?
- Compare your code against a working example or test case.

#### If the task feels too large

- Return to Phase 2 and break it down into smaller sub-tasks.
- Ask yourself: "What is the single next thing I can do?"
- Give yourself permission to do just that one thing.
- Consider pairing with a colleague to talk through the structure.

#### If you are struggling to focus

- Take a break. Step away from your screen for 5â€“10 minutes.
- Change your environment if possible (different desk, quieter space, noise-cancelling headphones).
- Write down what is on your mind. Sometimes externalising thoughts frees up focus.
- If sensory overload or anxiety is a factor, use any strategies that work for you without needing to explain them to others.

> ðŸ’¡ **You do not need to disclose why you are stuck:** When asking for help, you can simply describe the technical problem. You do not need to share the reason behind the block. Saying "I've been looking at this for 15 minutes and I'm not making progress â€“ can I talk it through?" is a professional and effective way to ask for support.

---

## Phase 5 â€“ Review and Complete

Before marking the task as done, work through this checklist to confirm quality and completeness.

### 5.1 Self-review checklist

- [ ] All acceptance criteria from Phase 1 are met
- [ ] Code runs without errors in the development environment
- [ ] Unit tests pass (or new tests have been written)
- [ ] Edge cases and error handling are covered
- [ ] Code follows team style guide and naming conventions
- [ ] No hardcoded values, secrets, or debug code remain
- [ ] Code is readable: meaningful variable names, clear logic, comments where needed
- [ ] Related documentation has been updated if required

### 5.2 Prepare for code review

Write a clear pull request or merge request description that includes:

- What the change does and why
- How to test it
- Any design decisions or trade-offs you made (use your decision log from Phase 3)
- Anything the reviewer should pay particular attention to

> ðŸ’¡ **Code review is collaborative, not evaluative:** Review feedback is about the code, not about you. If feedback is unclear, ask the reviewer to be more specific. If you disagree with feedback, it is appropriate to explain your reasoning calmly and discuss alternatives.

---

## Phase 6 â€“ Reflect and Grow

Reflection strengthens your skills and builds confidence over time. Complete this section after finishing the task.

### 6.1 Task reflection

| Question                        | Response |
|---------------------------------|----------|
| **What went well?**             |          |
| **What was difficult?**         |          |
| **What would I do differently?**|          |
| **What did I learn?**           |          |
| **Skills I used**               |          |
| **Skills I want to develop**    |          |

### 6.2 Personal development goals

Use this space to set 1â€“3 specific, achievable goals for your next task. These are for you. Share them with your manager in one-to-ones if you choose to.

| # | Goal | How I'll Practise | Target Date |
|---|------|-------------------|-------------|
| 1 |      |                   |             |
| 2 |      |                   |             |
| 3 |      |                   |             |

> ðŸ’¡ **Owning your development:** You are the expert on how you work best. If particular tools, environments, routines, or communication methods help you perform at your best, share that with your team. Advocating for what you need is a sign of professionalism and self-awareness.

---

## Appendix â€“ Communication Templates

Use these templates when you need to communicate about your work. Adapt them to your own voice.

### A.1 Asking for clarification

> Hi [name],
>
> I'm working on [task name]. I want to make sure I understand the requirement correctly.
>
> My understanding is: [your interpretation].
>
> Could you confirm whether that's correct, or let me know if I'm missing something?
>
> Thanks, [your name]

### A.2 Asking for help

> Hi [name],
>
> I'm stuck on [specific problem]. I've tried [what you've tried].
>
> The error / behaviour I'm seeing is: [description].
>
> Would you be able to take a look when you have a moment, or suggest where I might look next?
>
> Thanks, [your name]

### A.3 Flagging a blocker

> Hi [name / team],
>
> I'm currently blocked on [task name] because [specific reason].
>
> What I need to move forward: [specific request].
>
> In the meantime, I'll [what you'll do while waiting, or say "I'll move on to [other task]"].
>
> Thanks, [your name]

---

> **A final note:** Everyone approaches work differently. This task sheet exists to provide structure for those who find it helpful, and a reference for anyone who wants it. There is no single "correct" way to work. Use the parts that serve you, adapt the parts that don't, and communicate openly about what helps you do your best work.
