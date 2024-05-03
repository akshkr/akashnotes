### Introduction

Imagine you're trying to understand a long story or reading a novel. RNNs (Recurrent Neural Networks) and GRUs (Gated Recurrent Units) work a bit like reading the story word by word, remembering what you've read so far, and updating your understanding as you go along. But there's a problem: they can forget important details from earlier in the story as the story gets longer. It's a bit like having a bad memory when the story becomes too long.

RNNs and GRUs struggle with long stories because they have trouble keeping track of all the details. They might forget important information as the story progresses, making it harder for them to understand the whole picture. They also take a long time to train because they have to process the story word by word, which can be slow and inefficient.

First introducted in a paper - [Attention is all you need](https://arxiv.org/pdf/1706.03762), Transformers are a breakthrough in natural language processing, offering a novel approach to understanding and generating text.  Unlike traditional models such as RNNs and GRUs, which process data sequentially, transformers are like reading the entire story at once and understanding all the relationships between the words right from the start. This is achieved through self-attention mechanisms, enabling the model to weigh the importance of different words in relation to each other. By considering the context of the entire sequence at once, transformers can capture long-range dependencies and complex relationships between words more effectively. This holistic approach not only improves performance but also speeds up training due to parallel processing. As a result, transformers have become the cornerstone of many NLP tasks, from language translation to text generation, revolutionizing how machines comprehend and produce human language.

### Architecture

![Transformers](/data/assets/llms/transformers.png)


#### Input embedding layer

The input embedding layer of a transformer model is the initial stage where the model learns representations of each word in the input sequence. It transforms each word into a high-dimensional vector, capturing its semantic meaning and contextual information. This process is crucial because it converts raw text data into a format that the model can understand and process effectively.

![Input Embedding](/data/assets/llms/input_embedding.png)

In simpler terms, think of the input embedding layer as a translator that converts words into a language that the transformer model can comprehend. Each word is transformed into a unique vector representation based on its meaning and context within the sentence. These vector representations form the input for the subsequent layers of the transformer model, allowing it to perform tasks such as language understanding, translation, and text generation.

The input embedding layer is typically initialized randomly and fine-tuned during the training process to better capture the semantics of the input text. By learning meaningful representations of words, the transformer model can better understand the relationships between them, enabling more accurate and context-aware predictions.


#### Positional encoding layer

The positional encoding layer is a critical component of transformer models, designed to provide the model with information about the position of words in a sequence. Unlike recurrent neural networks (RNNs) or convolutional neural networks (CNNs), transformers do not inherently understand the order of words in a sequence. Therefore, positional encoding is added to the input embeddings to give the model a sense of sequence order.

![Positional encoding](/data/assets/llms/positional_encoding.png)

Positional encoding is typically implemented using trigonometric functions such as sine and cosine functions. These functions generate a set of fixed-length vectors, with each vector representing a specific position in the sequence. These vectors are then added to the input embeddings, creating unique representations for each word based on both its meaning and its position in the sequence.

In simpler terms, positional encoding is like giving each word in a sentence a special marker that tells the model where it belongs in the sentence. This helps the model understand the sequential order of words and capture their relationships more accurately.


#### Encoder layer

The encoder layer in transformer models processes the input sequence of words and converts it into a set of meaningful representations. It achieves this by analyzing the relationships between words in the sequence, capturing important contextual information, and extracting relevant features. The output of the encoder layer contains rich information about the input sequence, which can be further utilized for various tasks such as language understanding, translation, or text generation. Essentially, the encoder layer serves as the backbone of the transformer model, enabling it to effectively process and understand sequential data.

![Encoder](/data/assets/llms/encoder.png)

Let's break down the key components:

1. **Self-Attention Mechanism**: This is the core of the encoder layer. It allows the model to weigh the importance of each word in the input sequence based on its relationship with other words. By attending to different parts of the sequence simultaneously, the model can capture dependencies between words regardless of their position in the sequence.
2. **Multi-Head Attention**: To enhance its ability to focus on different aspects of the input sequence, the self-attention mechanism is often employed multiple times in parallel, each focusing on a different set of learned parameters. This allows the model to capture various types of information and combine them effectively.
3. **Feedforward Neural Network**: After the self-attention mechanism, the encoded representations pass through a feedforward neural network. This network applies non-linear transformations to the representations, allowing the model to learn complex patterns and relationships in the data.
4. **Residual Connections and Layer Normalization**: To facilitate training and improve the flow of gradients through the network, residual connections and layer normalization are often applied after each sub-layer. Residual connections allow the input to bypass the sub-layer and be directly added to its output, while layer normalization helps stabilize the training process by normalizing the activations.

#### Self-attention layer

![Self-attention](/data/assets/llms/self-attention.png)

Let's start with a single attention head. Suppose we have an input sequence consisting of four words: ["I", "love", "natural", "language"].

> Explain with matrix and diagram

In a single attention head, we compute the attention scores between each word and all other words in the sequence. For example, the attention score for the word "love" might indicate how much attention it should pay to each of the other words. These attention scores are then used to compute a weighted sum of the input sequence, where each word is weighted according to its relevance to the current word. This process allows the model to focus on different parts of the input sequence, capturing dependencies between words.

In multi-headed attention, we perform the attention operation multiple times in parallel, each with its own set of learnable parameters. For example, we might have four attention heads. Each attention head computes its own set of attention scores between each word and all other words in the sequence. This means that each attention head can focus on different aspects of the input sequence simultaneously, capturing different relationships between words such as syntactic structure, semantic meaning, word order, and so on.
After computing attention scores for each attention head, we concatenate the results and apply a linear transformation to obtain the final output of the multi-headed attention layer. By conducting multiple attention operations in parallel, the multi-headed attention mechanism enables the model to capture a diverse range of information from the input sequence, leading to more robust representations and better performance on downstream tasks.