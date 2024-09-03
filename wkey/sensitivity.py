# List of wake words including EBO keywords
wake_words = [
    'Hey Google', 'Porcupine', 'Jarvis', 'Blueberry', 'Alexa', 'Hey Siri', 'Americano',
    'ok google', 'computer', 'bumblebee', 'grapefruit', 'grasshopper', 'hey barista',
    'pico clock', 'picovoice', 'terminator'
]

# Dictionary to store the count of each wake word
wake_word_count = {}

# Count the occurrences of each wake word
for word in wake_words:
    if word in wake_word_count:
        wake_word_count[word] += 1
    else:
        wake_word_count[word] = 1

# Print the count of each wake word
for word, count in wake_word_count.items():
    print(f"{word}: {count}")
