original_audio = "The logs you're seeing are normal startup logs from the Vosk library as it loads the model and its components. These logs indicate that the model has been successfully loaded, and it's ready for speech recognition tasks. However, if your script just stops here without proceeding to recognize speech, it could be because the script is now waiting for audio input to process.The Vosk model you're using, vosk-model-small-en-us-0.15, does not have a specific wake word."

processed_transcript = "The ground state method of the whisper model class turns a typical containing generator over  class type segments and an instance of transcription info.  You need to reiterate over the sequence to concatenate this text for the finite  glass state.  Ensure that the whisper model utilization matches the actual class and with the names  for the master display library.  The provided code as used whisper model is correctly class for initializing the model,  which may need to be adjusted based on the actual library usage.  This code simply assumes that the class type can directly accept an umpire process  or uiner process or u.  As it is input, you may need to adjust the part if the vector accepts."

unprocessed_transcript = "The transitive method of the whisper model class turns into pull containing generator over  transitive segments and an instance of transcription info.  You need to iterate over the segments to concatenate this text for the final transcript.  Ensure that the whisper model initialization matches the actual class and with that name  for the faster whisper library.  The provided code assumes whisper model is correctly class for initializing the model,  which may need to be adjusted based on the actual library usage.  This force-tempered assumes that the transitive method can directly accept an upright array processed audio and a process audio.  As it is input, you may need to adjust the part if the method accepts."


Processed_Audio_Transcript_tiny="the logs you are seeing the apartment start up lots of was library as a lot of also martin it's components these logs indicate that the martin has been successfully order to and thirty four speech ago we shouldn't cost of living your grip just jobs here we don't proceeding though the good a speech it could be because this group these how waiting for arguing with the process the asked model you are using was model does not have a specific week or"

Unprocessed_Audio_Transcript_tiny=" The logs you are seeing are normal startup logs for BOSQ library as it loads and model  and its components.  These logs indicate that the model has been successfully loaded and it's ready for speech recognition tasks.  However, if your script just stops here without proceeding to recognize speech,  it could be because the script is now waiting for audio input to process.  The BOSQ model you are using, BOSQ model does not have a specific record."


Processed_Audio_Transcript_medium="  class returns a tuple containing a generator over transcribed segments and an instance  of transcription info.  You need to iterate over the segments to concatenate their tricks for the final transcript.  Ensure that the whisper model initialization matches the actual class and method names  for the Oster whisper library.  The provided code assumes whisper model is correct class for initializing the model,  which may need to be adjusted based on the actual library usage.  This code snippet assumes that the transcription method can directly accept a NumPy array  processed audio and unprocessed audio as its input.  You may need to adjust this part if the method expects."

Unprocessed_Audio_Transcript_medium= " class returns a tuple containing a generator over transcribed segments and an instance  of transcription info. You need to iterate over the segments to concatenate their tricks  for the final transcript. Ensure that the whisper model initialization matches the actual  class and method names for the faster whisper library. The provided code assumes whisper  is correct class for initializing the model, which may need to be adjusted based on the  actual library usage. This code snippet assumes that the transcription method can directly  accept the numpy array processed audio and unprocessed audio as its input. You may need  to adjust this part if the method expects."



processed_transcript_v3 = "The transcribe method of the Whisper Model class returns a tool containing a generator over transcribed segments and an instance  of transcription info.  You need to iterate over the segments to concatenate their text for the final transcript.  Ensure that the whisper model initialization matches the actual class and method names  for the foster whisper library.  The provided code assumes whisper model is correct class for initializing the model,  which may need to be adjusted based on the actual library usage.  This code snippet assumes that the transcription method can directly accept a NumPy array of  processed audio and unprocessed audio as its input.  You may need to adjust this part if the method expects."

unprocessed_transcript_v3= "The transcribe method of the Whisper Model class returns a tuple containing a generator over transcribed segments and an instance  of transcription info. You need to iterate over the segments to concatenate their text  for the final transcript. Ensure that the whisper model initialization matches the actual  class and method names for the faster whisper library. The provided code assumes whisper  model is correct class for initializing the model, which may need to be adjusted based  on the actual library usage. This code snippet assumes that the transcription method can  directly accept a NumPy array processed audio and unprocessed audio as its input. You may  need to adjust this part if the method expects."



processed_transcript_large =" class returns a tool containing a generator over transcribed segments and an instance  of transcription info.  You need to iterate over the segments to concatenate their text for the final transcript.  Ensure that the whisper model initialization matches the actual class and method names  for the foster whisper library.  The provided code assumes whisper model is correct class for initializing the model,  which may need to be adjusted based on the actual library usage.  This code snippet assumes that the transcription method can directly accept a NumPy array of  processed audio and unprocessed audio as its input.  You may need to adjust this part if the method expects."

unprocessed_transcript_large = " class returns a tuple containing a generator over transcribed segments and an instance  of transcription info. You need to iterate over the segments to concatenate their text  for the final transcript. Ensure that the whisper model initialization matches the actual  class and method names for the faster whisper library. The provided code assumes whisper  model is correct class for initializing the model, which may need to be adjusted based  on the actual library usage. This code snippet assumes that the transcription method can  directly accept a NumPy array processed audio and unprocessed audio as its input. You may  need to adjust this part if the method expects."


processed_transcript_small =" The transcribe method of the Whisper model class returns a tuple containing a generator  over transcribed segments and an instance of transcription info.  You need to iterate over the segments to concatenate the text for the final transcript.  Ensure that the Whisper model visualization matches the actual class and method names  from the faster Whisper library.  The provided code assumes Whisper model is the correct class for initializing the model  which may need to be adjusted based on the actual library use.  The code snippet assumes that the transcribed method can be directly accepted at NumPy array  processed audio and unprocessed audio as its input.  You may need to adjust this part if the method expects."


unprocessed_transcript_small = " The transcribe method of the Whisper model class returns a tuple containing a generator  over transcribed segments and an instance of transcription info.  You need to iterate over the segments to concatenate the text for the final transcript.  Ensure that the Whisper model initialization matches the actual class and method names  from the faster Whisper library.  The provided code assumes Whisper model is the correct class for initializing the model  which may need to be adjusted based on the actual library use.  The code snippet assumes that the transcribed method can be directly accept a numpy array  processed audio and unprocessed audio as its input.  You may need to adjust this part if the method expects."

def count_mistakes(original, transcript):
    original_words = set(original.split())
    transcript_words = set(transcript.split())
    mistakes = len(original_words.symmetric_difference(transcript_words))
    return mistakes

processed_mistakes = count_mistakes(original_audio, processed_transcript)
unprocessed_mistakes = count_mistakes(original_audio, unprocessed_transcript)

print("Mistakes in processed transcript:", processed_mistakes)
print("Mistakes in unprocessed transcript:", unprocessed_mistakes)





from difflib import SequenceMatcher

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

processed_similarity = similarity(original_audio, processed_transcript)
unprocessed_similarity = similarity(original_audio, unprocessed_transcript)

print(processed_similarity, unprocessed_similarity)



processed_similarity = similarity(original_audio, Processed_Audio_Transcript_tiny)
unprocessed_similarity = similarity(original_audio, Unprocessed_Audio_Transcript_tiny)

print("Processed_Audio_Transcript_tiny",processed_similarity, unprocessed_similarity)


processed_similarity = similarity(original_audio, processed_transcript_small)
unprocessed_similarity = similarity(original_audio, unprocessed_transcript_small)

print(processed_similarity, unprocessed_similarity)



processed_similarity = similarity(original_audio, Processed_Audio_Transcript_medium)
unprocessed_similarity = similarity(original_audio, Unprocessed_Audio_Transcript_medium)

print(processed_similarity, unprocessed_similarity)



processed_similarity = similarity(original_audio, processed_transcript_v3)
unprocessed_similarity = similarity(original_audio, unprocessed_transcript_v3)

print(processed_similarity, unprocessed_similarity)


processed_similarity = similarity(original_audio, processed_transcript_large)
unprocessed_similarity = similarity(original_audio, unprocessed_transcript_large)

print(processed_similarity, unprocessed_similarity)