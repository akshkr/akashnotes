Weight initialization is a procedure to set the weights of a neural network to some values that defines the starting point for the optimization.
Generally we follow some simple heuristics to initialize weights such as [-0.3, 0.3], [0, 1], [-1, 1]. The choice of weight initialization method depends on the activation function used in the network. Lets look at few techniques to initialize weights in a network.

### Glorot or Xavier initialization

The method aims to keep the variance of activations and gradients approximately the same for each layer, so as to ensure that the network can learn effectively.

This method sets a layer's weight to values chosen from a uniform probablity distribution between
$$ [-\frac{1}{\sqrt{n}}, \frac{1}{\sqrt{n}}] $$

#### Normalized xavier initialization

This is a slight modification from xavier initialization. We take random number from a uniform probability distribution between

$$[-\frac{\sqrt{6}}{\sqrt{n_{i} + n_{i+1}}}, \frac{\sqrt{6}}{\sqrt{n_{i} + n_{i+1}}}] $$

where ni is the number of incoming connections and ni+1 is the number of outgoing connections. This initialization method should only be used with sigmoid or tanh activation function and not with ReLU activation function.

### Kaiming / He initialization

Unlike Glorot initialization, He initialization is only used with ReLU activation function and not with sigmoid and tanh. In this initialization we pick a number from a gaussian probability distribution with mean 0 and standard deviation of root(2/n).

Let's try a simplistic approach to understand why this kind of standard deviation is needed.

- Let's say we've 512 input nodes and 256 nodes in the next layer.

- each has mean 0 and std 1 and when summed - 512. It follows that these 512 product would have mean of 0 and variance of 512 i.e. std of root(512).

- we want the std to be 1 so we divide all the values with root(512). Now each element will have variance of 1/root(512). Therefore y will have variance of 1.

- Since ReLU removes the negative weight the standard deviation of He initialization is sqrt(2/n).


#### References

- Kaiming : https://arxiv.org/pdf/1502.01852.pdf