import numpy as np
import matplotlib.pyplot as plt

np.random.seed(42)


# fourier series expansion of f(x) = x on the interval [-1, 1]
figure = plt.figure(figsize=(8, 4.125))
l = np.pi

x = np.linspace(-1, 1, 500)
y = x  # f(x)

a_0 = 1/l * np.trapezoid(y, x, dx=1/100)

y_fourier = np.zeros(len(x)) + a_0/2

for n in range(1, 100):

    figure.clear()
    axis = figure.subplots()

    axis.plot(x, y_fourier)
    axis.grid()
    plt.draw()
    plt.pause(0.05)

    a_n = 1/l * np.trapezoid(y * np.cos(n*np.pi*x/l), x, dx=1/100)
    b_n = 1/l * np.trapezoid(y * np.sin(n*np.pi*x/l), x, dx=1/100)
    fourier_term = a_n*np.cos(n*np.pi*x/l) + b_n * np.sin(n*np.pi*x/l)

    y_fourier = np.add(fourier_term, y_fourier)

y_fourier

plt.show


# monte carlo integration of the same function

def estimate_pi(n_samples: int = 100_000) -> float:
    x = np.random.rand(n_samples)
    y = np.random.rand(n_samples)

    inside = (x**2 + y**2) <= 1.0

    pi_estimate = 4*np.mean(inside)

    return pi_estimate


if __name__ == "__main__":
    np.random.seed(0)
    print(f"pi = {estimate_pi(1_000_000):.5f}")
