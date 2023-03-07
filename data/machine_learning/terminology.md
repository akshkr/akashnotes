Here we will be going through some basic terminologies that we will be using during our entire learing. Feel free to skip it if you know them.

#### Hypothesis function

A hypothesis is a function that best describes the target in supervised machine learning. In other words, a hypothesis function is typically used to represent a model that predicts the outcome of a particular task or problem, such as classification or regression. The hypothesis that an algorithm would come up depends upon the data and also depends upon the restrictions and bias that we have imposed on the data.

For example the hypothsis function linear regression uses to predict output in case of a single variable is:

$$ \hat{y} = h_{\theta}(x) = \theta_{0} + \theta_{1}x $$

#### Features / independent variables

A feature or an independent variable is a measurable property or characteristic of the data that is used as input to a machine learning model. It is also referred to as a predictor variable.

For example, if we are building a machine learning model to predict house prices, some of the features might include the size of the house, the number of bedrooms, the location, the age of the house, and so on. These features are the inputs that the machine learning model uses to make predictions.

Features can be of different types, such as numerical, categorical, or text-based. Numerical features are continuous or discrete numerical values, such as the price of a house or the number of bedrooms. Categorical features represent non-numerical values, such as color, type of vehicle, or location. Text-based features are usually extracted from natural language data, such as sentiment analysis or topic modeling.

#### Target / Dependent variable

A dependent variable is the output or target variable that the machine learning model is trained to predict. It is also referred to as the response variable.

For example, if we are building a machine learning model to predict house prices, the dependent variable would be the price of the house. The dependent variable can be of different types, depending on the problem being solved. For example, if we are building a binary classification model to predict whether an email is spam or not, the dependent variable would be binary, taking on values of 0 or 1. If we are building a regression model to predict the sales of a product, the dependent variable would be continuous, taking on any real value.

#### Training

Training refers to the process of teaching a machine learning model to make predictions by showing it examples of data. The goal of training is to enable the machine learning model to generalize to new, unseen data by learning the underlying patterns and relationships in the training data.

During the training process, the machine learning model uses an algorithm to learn from the input features and their corresponding output labels. The data used in training is called **training data**.

#### Test

Once the training is complete, the model is evaluated on a separate set of data called the test data. The performance of the model is measured using metrics such as accuracy. The test data helps to ensure that the machine learning model has learned to generalize to new data and is not overfitting to the training data.

#### Overfitting

Overfitting is a common problem in machine learning where a model performs well on the training data but poorly on new, unseen data. This happens when the machine learning model is too complex and captures the noise and idiosyncrasies of the training data, rather than the underlying patterns and relationships that generalize to new data.

When overfitting happens in a model, you might see the training accuracy to be too high and test accuracy to be low.

#### Cross-validation

Cross-validation is a technique that involves splitting the data into training and validation sets and evaluating the model's performance on the validation set during training. This helps to identify when the model is starting to overfit and allows us to adjust the model's hyperparameters accordingly.

#### Hyperparameters

Hyperparameters are parameters in a machine learning model that are set before training and cannot be learned from the data. They control the behavior of the machine learning algorithm and affect the performance of the model. Hyperparameters are different from the model's parameters, which are learned during training and updated to minimize the loss function. The model's parameters include the weights and biases in a neural network.

Examples of hyperparameters include the learning rate, the number of hidden layers in a neural network, the number of trees in a random forest, the regularization parameter, the number of iterations or epochs, and the batch size. Choosing the right hyperparameters can significantly affect the performance of the machine learning model. If the hyperparameters are set incorrectly, the model may overfit or underfit the data, resulting in poor performance.

