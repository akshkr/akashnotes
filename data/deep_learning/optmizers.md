Optimizers in deep learning are algorithms that adjust the model parameters to minimize a loss function.

### Gradient descent optimizer

repeat until convergence:
$$ \theta_{j} := \theta_{j} - \alpha \frac{\partial }{\partial \theta_{j}} J(\theta) $$
for j = 0 .. n

#### Batch gradient descent

Batch gradient descent is an optimization algorithm that updates the model's parameters by computing the gradients of the loss function with respect to the model's parameters for the **entire training dataset**. We take average of the gradients of all the training examples and then use the mean to update our parameter.
The only drawback of this method is that if the data is too large, converging might take more time and high memory utilization.

#### Stochastic gradient descent

Stochastic gradient descent (SGD) is a variant of gradient descent that uses a single training example to update the model's parameters at each iteration. This makes the algorithm very sensitive to the choice of the training examples, which can sometimes lead to suboptimal solutions. However, SGD has the advantage of being computationally efficient and can also escape local minima more easily than batch or mini-batch gradient descent.

#### Mini-batch gradient descent

Mini-batch divides the training dataset into small subsets called mini-batches. The model's parameters are then updated using the gradients of the loss function with respect to the model's parameters, calculated using a single mini-batch. This allows the model to make faster progress towards the minimum of the loss function, as the gradients are calculated more frequently.

Here we need to find the optimal size of batch such that it doesn't overshoot global minima and doesn't get stuck in local minima.

Now to overcome the issue or say optimize gradient descent algorithm, there more multiple tweaks done to improvise on the accuracy and learning rate of the model.

### Momentum

The basic idea behind momentum is to add a term to the updates that accumulates the past gradients. This term acts as a "memory" of the past gradients, which can help the optimizer to move more smoothly through the parameter space.

The first step is to track the gradient accumulation so called Velocity V.

$$ V(t) = \beta V(t-1) + (1 - \beta)\bigtriangledown J(\theta) $$

Initially, the velocity is 0. Then, everytime we calulate the gradient and keep expontial moving average like above. The momentum optimizer uses a hyperparameter, often denoted by the Greek letter beta (β), which controls the weight of the past gradients in the updates. A high value of beta (e.g. 0.9) means that the optimizer will pay more attention to the past gradients, while a low value (e.g. 0.1) means that the optimizer will pay more attention to the current gradients.

Now for the next step:

$$ \theta = \theta - \alpha*V(t) $$

If you observe, momentum optmizer has just replaced gradient by exponential moving average of gradient.

### Nesterov accelerated gradient descent

Here we give the momentum term a kind of prescience. For the derivative of cost function, instead of θ, we compute θ−α∗V(t), which gives us an approx of next position of the parameter. So the velocity terms is modified as,

$$ V(t) = \beta V(t-1) + (1 - \beta)\bigtriangledown J(\theta - \beta V(t-1)) $$

Momentum first computes the gradient annd then makes a big jump in the direction of accumulated gradient. NAG first makes a big jump in the direction of accumulated gradient and then makes correction.

### Adagrad - Adaptive gradient algorithm

Adagrad adapts the learning rate for each parameter individually, by dividing the learning rate by the square root of the sum of the squares of the gradients for that parameter.

The gradient at time t:
$$ g_{t, i} = \bigtriangledown_{\theta}J(\theta_{t, i})$$

Storing square of gradients:

$$ G_{t, i} = G_{t-1, i} + (g_{t-1, i})^{2} $$

Optimize learning rate by dividing with the accumulated term:

$$ \theta_{t+1, i} = \theta_{t, i} - \frac{\alpha}{\sqrt{G_{t, i} + \epsilon}}.g_{t, i} $$

This means that Adagrad will have a higher learning rate for parameters that have not been updated as much (since accumulated gradient for less frequently updated parameter will be lesser) and a lower learning rate for parameters that have been updated frequently (since accumulated gradient for more frequently updated parameter will be higher decreasing the learning rate). This allows the algorithm to converge more quickly for sparse data. Epsilon is just for numerical stability.

#### Advantages

- Well suited for sparse data, since update is more for less frequently occuring data.

- Removes the need of manually tuning learning rate.

#### Disadvantages

One downside of Adagrad is that the learning rate will decrease over time, which may cause the model to converge too slowly. This can be addressed by either increasing the initial learning rate or decreasing the learning rate over time.

### RMS prop - Root Mean Square Propagation

In adagrad if we just add a decaying parameter i.e. moving average of the squared gradients instead of average.

So in the storing of gradient step, it is modified to:

$$ G_{t, i} = \beta * G_{t-1, i} + (1 - \beta) * (g_{t-1, i})^{2} $$

The use of the moving average is that it helps to prevent the learning rate from becoming too small over time, as it does with Adagrad.

### Adadelta

Adadelta is an extension of Adagrad that seeks to reduce its aggressive, monotonically decreasing learning rate. Instead of accumulating all past squared gradients, Adadelta restricts the window of accumulated past gradients to some fixed size w.

### Adam - Adaptive momentum estimation

The idea is to mix SGD with momentum and adaptive learning from RMS prop.

Estimates of first moment (mean) -

$$ m_{t} = \beta_{1} m_{t-1} + (1 - \beta_{1})\bigtriangledown w_{t}$$

Estimates of second moment (variance) -

$$ v_{t} = \beta_{2} v_{t-1} + (1 - \beta_{2})(\bigtriangledown w_{t})^{2} $$

Bias correction -

$$ \hat{m_{t}} = \frac{m_{t}}{1 - \beta_{1}^{t}} $$

$$ \hat{v_{t}} = \frac{v_{t}}{1 - \beta_{2}^{t}} $$

This step helps ensure that the moving averages are accurate even at the start of the optimization process, before the averages have had time to stabilize.

Optimization step -

$$ \theta_{t+1} = \theta_{t} - \frac{\alpha}{\sqrt{\hat{v_{t}} + \epsilon}}.\hat{m_{t}} $$

#### Advantages

- This method is fast and converges rapidly.
- Recifies vanishing learning rate and high variance.

#### References

- https://arxiv.org/abs/1212.5701