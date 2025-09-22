# New graph (Url Crawler Graph)

# We search for the url of the biography of an author.
# Ex: Henry Miller https://en.wikipedia.org/wiki/Henry_Miller

# Url is crawled and the content is divided into chunks.
# chunks are separated into categories
# We merge the chunks into single variables called events_summary
# events_summary is a string of all the events that happened to the author.

# We clean further this events with clean and order events prompt and then we structure them into a JSON object.

# We obtain a json of all the structured events.

# Example of events_summary:
# "1990 - Born in USA "

# Example of structured events:
# [
#   {
#     "name": "Birth of Henry Miller",
#     "description": "Henry Miller was born in USA on 1990-01-01",
#     "date": {
#       "year": 1990,
#       "month": 1,
#       "day": 1
#     },
#     "location": "USA"
#   }
# ]

# Supervisor graph.

# The supervisor graph will be in charge of calling the tools like url_crawler
# The State will be the following.
# SupervisorState {
#   person_to_research: str
#   events: JSON object
# }

# After url crawler is called, we are going to merge both events, the ones from the current supervisor state and the ones from the url crawler.
# How will this be done?
# A prompt is sent that asks, "Which events from the supervisor state events are the same to the ones in the url crawler?"
# And then these events will be matched in the following way
# {
#   "supervisor_events": [
#     {
#       "id": "1",
#       "name": "Birth of Henry Miller",
#       "description": "Henry Miller was born in USA on 1990-01-01",
#       "date": {
#         "year": 1909,
#         "month": 1,
#         "day": 1
#       },
#       "location": "USA"
#     }
#   ]
# }

# url_crawler will return the following.
# {
#   "events": [
#     {
#       "id": "4",
#       "name": "Henry Miller, is born in a hosppital in Bushwick, Brooklyn",
#       "description": "Henry Miller was born in a hosppital in Bushwick, Brooklyn",
#       "date": {
#         "year": 1909,
#         "month": 1,
#         "day": 1
#       },
#       "location": "Bushwick, Brooklyn"
#     }
#   ]
# }


# The prompt will return the following.
# {
#   "matched_events": [
#     {
#       "supervisor_event_id": "1",
#       "url_crawler_event_id": "4",
#     }
#   ]
# }


# And then there will be another prompt that will go through each matched event and merge the information  with the most detailed information into the supervisor event.
# {
#   "merged_events": [
#     {
#       "id": "1",
#       "supervisor_event_id": "1",
#       "url_crawler_event_id": "4",
#       "name": "Birth of Henry Miller",
#       "description": "Henry Miller was born in USA on 1990-01-01 in a hospital in Bushwick, Brooklyn",
#       "date": {
#         "year": 1909,
#         "month": 1,
#         "day": 1
#       },
#       "location": "Bushwick, Brooklyn"
#     }
#   ]
# }

# And then we will update the supervisor state with the merged events.
# {
#   "events": [
#     {
#       "id": "1",
#       "name": "Birth of Henry Miller",
#       "description": "Henry Miller was born in USA on 1990-01-01 in a hospital in Bushwick, Brooklyn",
#     }
#   ]
# }


# The supervisor graph will also have another tool called further_event_research. The tool call will be another subgraph
# This subgraph will be in charge of looking at all the events in the supervisor state. Analyze which ones have missing information or could be extended.
# Then it will iterate through each of these events and will do the following.
# Will do a call to tavily/search_engine to get website that may know more about the event. And will update the event accordingly.


# Problem: How to decide if the tool url_crawler or further_event_research should be called?
# Let's do the following.
# there is another tool. url_finder, url_crawler, further_event_research.
# url_finder receives a response of possible relevant urls. Like: wikipedia, brittanica, etc.
# Then it analyzes how the overall of the events are, if there already a lot of events, then let's improve the events individually.
# If there are not a lot of events, then let's call url_crawler with one of the urls found in url_finder to get more events.

# So the overall flow could look like this
# url_finder -> url_crawler -> further_event_research
# Or
# url_finder (response: wikipedia, brittanica) -> url_crawler (wikipedia) -> url_crawler (brittanica) -> further_event_research -> further_event_research


# How to determine if the events have been thoruoughly investigated? Have all the information been found?
# Do something similar as in open_deep_research, where is possible to iterate multiple times and have a maximum of iterations.


## Would be cool if it's possible to pass a list of already completed events to the supervisor graph.
# And then the supervisor graph can decide if it needs to call the tools again.
