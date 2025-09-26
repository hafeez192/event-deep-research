## To make the AI agent to reserach authors work well I have made a couple of errors

I am tring to give to much context to the llm on each call, this makes response take too much.

I am converting to the final structure in the middle of the sub agent. The sub agent should be completely agonstic to the state of the overall graph.

This is the main point.

Now it's going to look like this.

1. Early Life & Background

Covers childhood, upbringing, family, education, and early influences that shaped the author.

2. Personal Life

Focuses on relationships, friendships, family life, places of residence, ethnicity/race, and notable personal traits or beliefs.

3. Career & Works

Details their professional journey: first steps into writing, major publications, collaborations, recurring themes, style, and significant milestones.

4. Legacy & Influence

Explains how their work was received, awards or recognition, cultural/literary impact, influence on other authors, and how they are remembered today.

The url is scraped. What then (In the research subgraph)??

The input state is the same, prompt and events (but these events are in the following manner)

events: {
personal: "- event1 - event2..."
early
career
legacy
}

1. The information is separated into events.
2. Each event is classified into one of these 4 categories.
3. The event is merged onto the running events from the main state but kept as a single string

This way the context for each section is smaller and we don't have to convert everything into years, location and json objects until the end.

No need for chunking as much.
