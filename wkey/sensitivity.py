transcript = """



Wake word 'Hey Barista' detected!
Wake word 'Terminator' detected!
Wake word 'Hey Siri' detected!
Wake word 'Jarvis' detected!
Wake word 'Hey Siri' detected!
Wake word 'Grasshopper' detected!
Wake word 'Blueberry' detected!
Wake word 'Bumblebee' detected!
Wake word 'Hey Google' detected!
Wake word 'Computer' detected!
Wake word 'Computer' detected!
Wake word 'Hey Google' detected!
Wake word 'Hey Google' detected!
Wake word 'Hey Google' detected!
Wake word 'Grasshopper' detected!
Wake word 'Jarvis' detected!
Wake word 'Porcupine' detected!
Wake word 'Bumblebee' detected!
Wake word 'Americano' detected!
Wake word 'Bumblebee' detected!
Wake word 'Grapefruit' detected!
Wake word 'Hey Google' detected!
Wake word 'Hey Google' detected!
Wake word 'Hey Google' detected!
Custom wake word 'Hey Llama' detected!
Custom wake word 'Hey Llama' detected!
Wake word 'Jarvis' detected!
Wake word 'Grasshopper' detected!
Wake word 'Americano' detected!
Wake word 'Americano' detected!
Wake word 'Pico Clock' detected!
Wake word 'Jarvis' detected!
Wake word 'Americano' detected!
Wake word 'Terminator' detected!
Wake word 'Bumblebee' detected!
Wake word 'Jarvis' detected!
Wake word 'Hey Siri' detected!
Wake word 'Jarvis' detected!
Wake word 'Alexa' detected!
Wake word 'Alexa' detected!


"""

wake_words = [
    "Hey Google",
    "Porcupine",
    "Jarvis",
    "Blueberry",
    "Alexa",
    "Hey Siri",
    "Americano",
    "ok google",
    "computer",
    "bumblebee",
    "grapefruit",
    "grasshopper",
    "hey barista",
    "pico clock",
    "picovoice",
    "terminator",
    "Hey Llama",
]

# Normalize transcript for consistent counting
normalized_transcript = transcript.lower()

# Normalize wake words for consistent counting
normalized_wake_words = [word.lower() for word in wake_words]

# Count occurrences of each wake word
wake_word_counts = {
    word: normalized_transcript.count(word) for word in normalized_wake_words
}

# Print the counts
for word, count in wake_word_counts.items():
    print(f"{word}: {count}")
