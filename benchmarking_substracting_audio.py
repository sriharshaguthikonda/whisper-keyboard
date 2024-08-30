"""
##    ##  #######     ##     ## ####  ######     ########  ######## ######## ######## ######## ########
###   ## ##     ##    ###   ###  ##  ##    ##    ##     ## ##          ##       ##    ##       ##     ##
####  ## ##     ##    #### ####  ##  ##          ##     ## ##          ##       ##    ##       ##     ##
## ## ## ##     ##    ## ### ##  ##  ##          ########  ######      ##       ##    ######   ########
##  #### ##     ##    ##     ##  ##  ##          ##     ## ##          ##       ##    ##       ##   ##
##   ### ##     ##    ##     ##  ##  ##    ##    ##     ## ##          ##       ##    ##       ##    ##
##    ##  #######     ##     ## ####  ######     ########  ########    ##       ##    ######## ##     ##
"""

import ollama
from sklearn.metrics.pairwise import cosine_similarity

# Load the Ollama embedding model (e.g., mxbai-embed-large)
model_name = "mxbai-embed-large"

# Input your original transcript
original_transcript = """so here are certain nice features you know by features i mean r is a browser and you can do everything that you can do in html and css so first of all you can see that there's a blinking paranthesis that's one of the rainbow parentheses and you can also see the corresponding 
parenthesis that's whitening color it also blinks the second thing is the hashtag in heading also blinks you can theoretically make the whole heading blink but it's very distracting when you work uh the third thing is that q line uh that's how it's named in the css that also blinks and you can uh find radio car series when you're 
scrolling up and down trying to do a lot of things in a large notebook and the final thing is yeah the key with the selected keyword 
uh blinking that's very helpful when you're working with last fight you can see yeah so many of them and obviously the whole pimped out look so you can find the exact file i'm using in the description and certain other details in the description you"""

# Input the first model's transcript
no_mic_transcript = """The hashtag is heading also links. You can theoretically make the whole heading link but it's very distracting. The third thing is that Q-Line. That's how it's named after here. There also blames and you can find radio car series when you're scrolling up and
 So here are some nice features in our. By features I mean I is a browser and you can do everything that you can do in HTML and CSS. So first of all you can see that there's a blinking
 The second thing is the hashtag is heading also blinks. You can theoretically make the whole heading blinked by it's very distracting.
 here the keyword, the selected keyboard blinking. That's very helpful when you're working at last rights, can see.
 that's how it's named in that exists. That also blinks and then you can find your cursaries when you're scrolling up and out, write a rule, a lot of things in a large notebook. And the final thing is yeah the keyword, the set the keyword blinking. That's very helpful."""

# Input the second model's transcript
sustract_transcript = """The hashtag is heading also links. You can directly make the whole heading blink where it's very designed and it's work. The third thing is that's why it's named in the CSS. There also links and you can find radio cars and see you're scrolling up and a lot.
 So here are some nice features in our features I mean how is your browser and you can do everything that you can do in HTML and CSS. So first of all you can see that there's a blinking
 The second thing is the hashtag is heading also blinks. You can really make the whole heading blink by the experience tracking in the world.
 here, the keyword, the keyboard, the click. That's very helpful when you're working at last fights, you can see.
 that's how it's named after that also blinks and then you can find made your cursories when you're school up and down trying to do a lot of things in a large notebook and the final thing is here the selected keyboard the selected keyboard blinking that's very helpful"""

# Generate embeddings
original_embedding = ollama.embeddings(model=model_name, prompt=original_transcript)[
    "embedding"
]
no_mic_embedding = ollama.embeddings(model=model_name, prompt=no_mic_transcript)[
    "embedding"
]
sustract_embedding = ollama.embeddings(model=model_name, prompt=sustract_transcript)[
    "embedding"
]


def calculate_cosine_similarity(embedding1, embedding2):
    return cosine_similarity([embedding1], [embedding2])[0][0]


similarity1 = calculate_cosine_similarity(original_embedding, no_mic_embedding)
similarity2 = calculate_cosine_similarity(original_embedding, sustract_embedding)

if similarity1 > similarity2:
    print("no_mic is more similar to the original.")
elif similarity2 > similarity1:
    print("sustract is more similar to the original.")
else:
    print("Both models have similar similarity scores.")
