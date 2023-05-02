### Introduction to Machine Learning
Machine learning is a field of computer science that focuses on developing algorithms and models that can learn patterns and insights from data, and use that knowledge to make predictions and decisions. In machine learning, an algorithm is trained on a dataset, and it uses statistical methods to identify patterns and relationships in the data. These patterns and relationships are then used to make predictions or decisions about new data.
Lets look at a formal definition - 

> A computer program is said to learn from experience E with respect to some class of task T and performance measure P, if its performance in T as measured by P improves with experience E.

### Types of machine learning algorithm

1. SUPERVISED LEARNING
    - Regression
    - Classification
2. UNSUPERVISED LEARNING
    - Clustering
    - Non-clusterinng
3. REINFORCEMENT LEARNING

### Supervised Learning
Supervised learning is a type of machine learning algorithm where the algorithm is trained on a labeled dataset, where the desired output is known for each input. The goal of supervised learning is to learn a function that can make accurate predictions on new, unseen data.

We split the labeled dataset is divided into two sets: a training set and a testing set. The training set is used to train the algorithm, while the testing set is used to evaluate the performance of the algorithm on new, unseen data. The algorithm is trained to learn a mapping function that takes an input and produces an output that matches the labeled data.

#### Regression

Regression is a type of supervised learning algorithm that is used to predict a continuous output variable based on one or more input variables. The goal of regression is to learn a mapping function that can accurately predict the output variable for new, unseen input values.

In regression, the output variable is continuous, which means that it can take on any value within a certain range. For example, in a simple linear regression problem, the output variable might represent the price of a house, which can take on any positive value. The input variables are also known as predictors or independent variables, and they can be either continuous or categorical.

#### Classification

Classification on the other hand is used to predict the categorical class labels of input data based on one or more input variables.

In classification, the output variable is categorical, which means that it can take on a limited number of values, such as "spam" or "not spam", "positive" or "negative", or "red", "green", or "blue".

### Unsupervised learning

Unsupervised learning is a type of machine learning algorithm that is used to find patterns or structure in unlabeled data. Unlike supervised learning, unsupervised learning algorithms do not have access to labeled examples that specify the correct output for each input. Instead, the algorithm is given a dataset and must identify patterns, structure, or relationships among the data points without any prior knowledge.

Clustering is one of the most common types of unsupervised learning algorithms. Clustering algorithms group similar data points together based on some measure of similarity or distance. Examples of clustering algorithms include k-means, hierarchical clustering, and density-based clustering.

Another type of unsupervised learning algorithm is dimensionality reduction, which is used to reduce the number of input variables while preserving as much of the original information as possible. Principal component analysis (PCA) is a popular dimensionality reduction technique that identifies the most important features in the data and represents the data in a lower-dimensional space.

Other types of unsupervised learning algorithms include anomaly detection, which is used to identify rare or unusual data points, and association rule mining, which is used to find relationships or dependencies among different variables in the data.

The performance of unsupervised learning algorithms is typically evaluated based on the quality of the output, such as the degree to which the data points are grouped together in meaningful clusters or the ability of the algorithm to identify rare or unusual data points.

### Reinforcement learning

Reinforcement learning is a type of machine learning where an agent learns to make decisions in an environment by trial and error. The agent takes actions and gets feedback in the form of rewards or penalties. The goal of the agent is to maximize the rewards it receives over time by learning a set of rules, or a policy, that tells it what action to take in each situation. Reinforcement learning can be used in many applications, like teaching robots to perform tasks, or helping computer programs make decisions.

Now, do you have an understanding of the various types of machine learning algorithms that are available? It's okay if you have any doubts; we will clear them up as we go through the algorithms and examples. Now, let's take a look at some terminologies that you may come across in machine learning.