Let's start with our first algorithm of machine learning - Linear Regression. This algorithm is used to predict target which is continuous in nature like price of house, temperate of a place, rating of a movie etc.

But before proceeding with the algorithm, let's understand a rough working of any supervised machine learning algorithm. An algorithm mainly consist of a hypothesis i.e. the function the model will apply on the features to get the output. We've a cost function which determines the accuracy of the model at any given time during the training. It's reasonable to say that the ultimate target of a learning is to minimize the cost. But how does the model minimizes the cost? Using the Optimiser. An optimizer is an algorithm that is used to update the parameters of a machine learning model during training in order to minimize the loss function. The optimizer determines the direction and magnitude of the updates to the model's parameters in each iteration of the training process. This was a rough idea of how any supervised machine learing algorithm works. Now let's try to understand one algorithm in detail.

### Types of Linear Regression

1. Univariate linear regression: single dependent and independent variable
2. Multiple regression: multiple independent and single dependent variable.
3. Multivariate regression: multiple independent and dependent variable

### Univariate linear regression

Univariate linear regression means that there is a single feature and a single target. Let's say you've to predict house price based on the size of the plot the house is constructed on. Let's look at the hypothsis function for it.

#### Hypothesis function

$$ \hat{y} = h_{\theta}(x) = \theta_{0} + \theta_{1}x $$

Here x is the size of plot and y cap is the price. θ's are the model parameters.

#### Cost function

$$ J(\theta_{0}, \theta_{1}) = \frac{1}{2m} \sum_{i=1}^{m}(\hat{y}_{i} - y_{i})^{2} $$

this is the function which calculates the error of the prediction while training. y cap in the predicted price and y is the actual price. 

- squared error function or mean squared error
- 1/2 is there to cancel the constant in derivative while computing gradient descent

#### Gradient descent optimizer

Repeat until convergence:
$$ \theta_{j} := \theta_{j} - \alpha \frac{\partial }{\partial \theta_{j}} J(\theta_{0}, \theta_{1}) $$

- α - learning rate : The learning rate is a hyperparameter that determines how much the weights of a model are updated during training. It is a scaling factor that controls how quickly the model learns from the data. If the learning rate is too small, the model may take a long time to converge, or it may get stuck in a suboptimal solution. On the other hand, if the learning rate is too high, the model may overshoot the optimal solution and oscillate around it or diverge. It is typically set through trial and error.

**The derivative of the cost function determines the direction and maginute of the update of θ**. Let's try to understand what exactly optimizer does to model parameters.

This is a graph of loss function with respect to θ.
![loss](/data/assets/machine_learning/loss_landscape_lr.png)

Initially we've a random value of θ, which means that we could be anywhere on this graph, but the final target is to reach to minimize the loss which is to reach to the bottom of this graph (red pointer). The optimiser updates the θ's iteratively such that the final value is at the bottom.

### Linear regression with multiple variables

#### Hypothesis function

$$ \hat{y} = h_{\theta}(x) = \theta_{0} + \theta_{1}x_{1} + \theta_{2}x_{2} + \theta_{3}x_{3} + \theta_{4}x_{4} + . . . + \theta_{n}x_{n} $$

vector form:
$$ \hat{y} = h_{\theta}(x) = \theta^{T}x $$

#### Cost function

$$ J(\theta) = \frac{1}{2m} \sum_{i=1}^{m}(\hat{y}_{i} - y_{i})^{2} $$

#### Optimizer
1. Gradient descent
Repeat until convergence:
$$ \theta_{j} := \theta_{j} - \alpha \frac{\partial }{\partial \theta} J(\theta) $$

2. Normal equation / Ordinary least square / Linear least square

$$ \theta = (X^{T}X)^{-1} X^{T}y $$

- No learning rate
- Slower when n is large O(n^3)
- No iteration needed
- Sum of residuals is 0
