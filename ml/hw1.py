import sys
import numpy as np


class LinearRegression:
    def __init__(self, learning_rate, iterations):
        self.learning_rate = learning_rate
        self.iterations = iterations

    def fit(self, X, Y):
        self.X = np.asarray(X, dtype=float)
        self.Y = np.asarray(Y, dtype=float).ravel()

        self.m, self.n = self.X.shape

        self.W = np.zeros(self.n)
        self.b = 0.0

        for _ in range(self.iterations):
            self.update_weights()

        return self

    def update_weights(self):
        Y_pred = self.predict(self.X)
        error = Y_pred - self.Y

        dW = (2 / self.m) * np.dot(self.X.T, error)
        db = (2 / self.m) * np.sum(error)

        self.W -= self.learning_rate * dW
        self.b -= self.learning_rate * db

    def predict(self, X):
        return np.dot(X, self.W) + self.b


exec(sys.stdin.read())
