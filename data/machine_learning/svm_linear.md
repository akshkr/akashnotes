The objective of Support Vector Machine is to find a hyperplane is a N - dimentional space (N - number of features) that classifies the data points.

Key characteristics and concepts of Support Vector Machines include:

Margin: The margin is the distance between the maximum-margin hyperplane and the nearest data points from each class. SVM aims to find the hyperplane that maximizes this margin, which helps improve the model's generalization and robustness.

![Support vector machine](/data/assets/machine_learning/support-vector-machine.png)

Support Vectors: These are the data points that are closest to the hyperplane and have the most influence on determining its position. Support vectors play a crucial role in defining the margin and, in turn, the SVM's decision boundary.

Kernel Trick: SVMs can handle linearly separable data as well as data that are not linearly separable in their original feature space. The kernel trick allows SVMs to transform the data into a higher-dimensional space where it may become linearly separable, even when it was not in the original feature space. Common kernels include linear, polynomial, radial basis function (RBF), and sigmoid kernels.

C Parameter: The regularization parameter "C" controls the trade-off between maximizing the margin and minimizing the classification error. A smaller C value encourages a wider margin but might allow some misclassification, while a larger C value reduces the margin but minimizes misclassification.

Now let's start with Linear SVM:

## Linear SVM

### Hypothesis function for a Linear SVM:

$$f(x) = \theta^T x + b$$

 
In this equation:

- `f(x)` represents the output of the SVM for the input feature vector `x`.
- `θ` is the weight vector that defines the orientation of the hyperplane.
- `x` is the input feature vector.
- `b` is the bias term that shifts the hyperplane away from the origin.

The prediction is made by evaluating the sign of `f(x)`:

- If `f(x) > 0`, the input `x` is classified as one class (typically +1).
- If `f(x) < 0`, the input `x` is classified as the other class (typically -1).

The parameters `w` and `b` are determined during the training process to find the hyperplane that best separates the training data into their respective classes with the maximum margin. The sign of `f(x)` is used to determine the class label of new, unseen data points during the testing or prediction phase.

### Cost function

$$J(\theta) = -\frac{1}{m}\sum_{i=1}^{n}y_{i}log(\hat{y_{i}}) + (1 - y_{i})log(1 - \hat{y_{i}}) $$