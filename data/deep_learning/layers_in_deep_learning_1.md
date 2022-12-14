## Dense Layer / Fully connected layer

Neurons of the layer are connected to every neuron of it's preceding layer.

### Advantages
- Changes the dimension of the vector.
- Adds non-linear property (through activation function).
- Produces output using every node in the previous layer (learn from every feature).
- Used for rotation, scaling and translation.


## Dropout layer

It randomly sets the outgoing edges of hidden units (neurons that make hidden layers) to 0 at each update of the training phase. Each unit is retained with a fixed probability p independent of other units. For input layer p = 1.

![Dropout layer](/data/assets/deep_learning/dropout.png)

While training without dropout layer, weights of neurons are tuned for specific features providing some specialization. If neurons are randomly dropped out of the network during training, the other neurons will have to step in and handle the representation required to make prediction for the missing values.

### Advantages
- It prevents overfitting.
- It prevents co-adaption of features i.e. a feature detector is helpful only in context of several other features.
- combined different networks efficiently.

### Refereces
- [Dropout layer](https://www.cs.toronto.edu/~rsalakhu/papers/srivastava14a.pdf)
- [Co-adaption of feature](https://arxiv.org/abs/1207.0580)
