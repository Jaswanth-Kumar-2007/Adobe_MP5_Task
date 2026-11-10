# IDEAS.md: How the Knowledge Buddy Can Use This Data

The Knowledge Buddy is a future student helper for the B.Tech DSAI programme at IIT Bhilai. This repo only prepares the data. It does not build the chatbot, and it does not use embeddings or an LLM yet.

## Three questions the buddy can answer well

**1. "What do I need to take before course X?"**
The buddy looks up the course in the prerequisites table and lists what it requires. It can also name the semester where the course appears in the programme plan, and it shows the source for each answer.
*Limit:* only a few prerequisites are recorded, and some point to courses outside our data. The buddy should say "not recorded" when it finds none.

**2. "Which courses teach a skill like Machine Learning?"**
The buddy searches the skills list, finds the linked courses, and shows each course's topics and credits.
*Limit:* the skill links come from keywords in the syllabus. They show what a course mentions, not how well it teaches it.

**3. "What does the course plan look like for a semester, and how many credits do I need?"**
The buddy reads the programme plan by semester and lists the courses and slots. It can quote the matching credit rule.
*Limit:* the rules are extracted text. They need a human check before the buddy calls them official.

## Questions the buddy cannot answer (yet)

| Question | Why not |
|---|---|
| "Am I eligible for a minor?" | It needs my CGPA and course history. We hold no student data, by design. |
| "Which electives are running this term?" | We have no live timetable or seat data. |
| "Which course is easiest or best for placements?" | We have no reviews, workload or outcome data. |
| "Which free NPTEL or MIT OCW course should I take?" | Our resource list is not verified for licences or topic links yet. |
| "What is the exact learning order for a full goal?" | Our prerequisite graph is incomplete. |
| "What should a Mechanical or ECE student study?" | We cover DSAI only. |

## How the buddy should behave

- Answer only from the records, and always show the source URL and the date it was retrieved.
- Say "not in my data" when something is missing. That is different from saying it is not true.
- Mark rules and eligibility as "needs verification" until a person checks them.
- Never decide a student's personal eligibility.

## What to add next

1. Check the rules against the source PDFs.
2. Add more prerequisite links.
3. Verify the resource licences and link each resource to a skill.
4. Add embeddings only after the data is checked.