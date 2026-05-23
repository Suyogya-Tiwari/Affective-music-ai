from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Dropout, LSTM, Concatenate, Activation, Embedding, Flatten
from tensorflow.keras.optimizers import Adam

def create_network(sequence_length, vocab_size, num_emotions=2):
    """
    Builds the Multi-Input LSTM Neural Network.
    Path A: The sequence of notes (Sequential data)
    Path B: The emotion ID integer (Embedding Layer)
    """
    # ---------------------------------------------------
    # PATH A: The Musical Notes (LSTM)
    # ---------------------------------------------------
    notes_in = Input(shape=(sequence_length, 1), name="notes_input")
    
    x1 = LSTM(256, return_sequences=True)(notes_in)
    x1 = Dropout(0.3)(x1)
    x1 = LSTM(256)(x1)
    notes_branch = Dropout(0.3)(x1)
    
    # ---------------------------------------------------
    # PATH B: The Emotion/Mood Label (Embedding)
    # ---------------------------------------------------
    mood_in = Input(shape=(1,), name="mood_input")
    
    # The Embedding layer mathematically represents each emotion as a 16-dimensional vector.
    # This automatically scales whether we have 2 emotions or 50.
    x2 = Embedding(input_dim=num_emotions, output_dim=16)(mood_in)
    x2 = Flatten()(x2)
    x2 = Dense(32, activation='relu')(x2)
    mood_branch = Dense(32, activation='relu')(x2)
    
    # ---------------------------------------------------
    # MERGE & PREDICT
    # ---------------------------------------------------
    combined = Concatenate()([notes_branch, mood_branch])
    
    y = Dense(128, activation='relu')(combined)
    y = Dropout(0.3)(y)
    
    y = Dense(vocab_size)(y)
    output = Activation('softmax', name="note_output")(y)
    
    model = Model(inputs=[notes_in, mood_in], outputs=output)
    model.compile(loss='categorical_crossentropy', optimizer=Adam(learning_rate=0.001))
    
    return model

if __name__ == "__main__":
    print("Building test model...")
    test_model = create_network(sequence_length=100, vocab_size=350, num_emotions=2)
    test_model.summary()
