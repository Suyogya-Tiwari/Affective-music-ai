from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Dropout, LSTM, Concatenate, Activation
from tensorflow.keras.optimizers import Adam

def create_network(sequence_length, vocab_size):
    """
    Builds the Multi-Input LSTM Neural Network.
    Path A: The sequence of notes (Sequential data)
    Path B: The mood label (0 for Happy, 1 for Sad)
    """
    # ---------------------------------------------------
    # PATH A: The Musical Notes (LSTM)
    # ---------------------------------------------------
    # The input shape is (sequence_length, 1) because we look at 'sequence_length' notes at a time
    notes_in = Input(shape=(sequence_length, 1), name="notes_input")
    
    # LSTMs are great for remembering long-term patterns in sequences
    x1 = LSTM(256, return_sequences=True)(notes_in)
    x1 = Dropout(0.3)(x1) # Dropout prevents the model from memorizing the exact songs (overfitting)
    x1 = LSTM(256)(x1)
    notes_branch = Dropout(0.3)(x1)
    
    # ---------------------------------------------------
    # PATH B: The Emotion/Mood Label
    # ---------------------------------------------------
    # A simple input for a single number (0 or 1)
    mood_in = Input(shape=(1,), name="mood_input")
    x2 = Dense(32, activation='relu')(mood_in)
    mood_branch = Dense(32, activation='relu')(x2)
    
    # ---------------------------------------------------
    # MERGE & PREDICT
    # ---------------------------------------------------
    # We combine the LSTM's memory of the notes with the requested mood
    combined = Concatenate()([notes_branch, mood_branch])
    
    # Final dense layers to figure out the prediction
    y = Dense(128, activation='relu')(combined)
    y = Dropout(0.3)(y)
    
    # The final output layer MUST have the exact same number of neurons as our 'vocab_size'
    # Softmax ensures all the output probabilities add up to 100%
    y = Dense(vocab_size)(y)
    output = Activation('softmax', name="note_output")(y)
    
    # Assemble the final model
    model = Model(inputs=[notes_in, mood_in], outputs=output)
    
    # We use 'categorical_crossentropy' because predicting a note is technically a classification problem
    model.compile(loss='categorical_crossentropy', optimizer=Adam(learning_rate=0.001))
    
    return model

if __name__ == "__main__":
    # A quick test to see if the model compiles and print a summary of the architecture
    print("Building test model...")
    test_model = create_network(sequence_length=100, vocab_size=350)
    test_model.summary()
