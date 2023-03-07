### Vanishing gradient

As more and more layers are added to neural network, the gradient of the loss approaches 0 making it impossible to train.

Activation functions like sigmoid and tanh squishes large input range to small space. Even for a large change in input there is a small change in output. By chain rule the derivative of each layer are multiplied down the network to compute the derivative of initial layer.

When n layers use activation functions like sigmoid, n small derivative are multiplied together. Thus gradient decreases exponentially and while backpropagation, the weights of initial layers are not updated.

#### Solution
1. Use ReLU activation function.
2. Use Batch normalization layer.
3. Redesign the network to reduce number of layers.
3. Weight initialization (Xavier initialization when sigmoid/tanh is used)
4. Residual networks (skip-nets).


### Exploding gradient

This is similar to vanishing gradient except the gradient increases to very large number rather diminishing. This happens usually when we use unbounded activation functions like ReLU. The explosion occurs through exponential growth by repeatedly multiplying gradients through the network layers that have values larger than 1.0.

#### Solution
1. Gradient clipping
2. Redesign the network to reduce number of layers.
3. Use activation function with bounded range.
4. Weight initialization (Kaiming/He initialization).