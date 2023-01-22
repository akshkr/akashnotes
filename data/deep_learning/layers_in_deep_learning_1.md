Now that we have covered the neural network basics and what a deep network is, let's go through the layers of the deep network.

## Dense Layer / Fully connected layer

Let's start with the simplest one. This is basically the layer we talked about in the neural network. The neurons of a dense layer are connected to every neuron of its preceding layer. Something like the image of standard neural nets below.

### Advantages
- Changes the dimension of the vector i.e. number of neurons changes at every layer changing the dimension of the input vector at every stage.
- Adds non-linear property (through activation function). The activation function allows neural networks to identify non-linear relations between the independent and dependent variables.
- Produces output using every node in the previous layer (learn from every feature).
- Used for rotation, scaling, and translation.


## Dropout layer

It randomly sets the outgoing edges of hidden units (neurons that make hidden layers) to 0 at each update of the training phase. Each unit is retained with a fixed probability p independent of other units. For input layer p = 1.

![Dropout layer](/data/assets/deep_learning/dropout.png)

While training without a dropout layer, the weights of neurons are tuned for specific features providing some specialization. Neurons are randomly dropped out of the network during training, the other neurons will have to step in and handle the representation required to make predictions for the missing values.

### Advantages
- It prevents overfitting.
- It prevents co-adaption of features i.e. a feature detector is helpful only in context of several other features.
- Combines different networks efficiently.

### Refereces
- [Dropout layer](https://www.cs.toronto.edu/~rsalakhu/papers/srivastava14a.pdf)
- [Co-adaption of feature](https://arxiv.org/abs/1207.0580)
