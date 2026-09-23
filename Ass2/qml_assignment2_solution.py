from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parent
FIGURES_DIR = ROOT / "figures"
FIGURES_DIR.mkdir(exist_ok=True)


EQUILIBRIUM_DISTANCE = 0.735
H2_COEFFICIENTS = {
    0.30: (-0.2253, 0.5678, -0.5678, 0.0908, 0.0908),
    0.40: (-0.5297, 0.5215, -0.5215, 0.0599, 0.0599),
    0.50: (-0.7382, 0.4834, -0.4834, 0.0264, 0.0981),
    0.60: (-0.8816, 0.4497, -0.4497, -0.0021, 0.1282),
    0.70: (-0.9810, 0.4192, -0.4192, -0.0132, 0.1584),
    0.735: (-1.0523732, 0.3979374, -0.3979374, -0.0112801, 0.1809312),
    0.80: (-1.0466, 0.3920, -0.3920, -0.0165, 0.1751),
    0.90: (-1.0858, 0.3677, -0.3677, -0.0165, 0.1867),
    1.00: (-1.1027, 0.3457, -0.3457, -0.0144, 0.1940),
    1.20: (-1.1015, 0.3070, -0.3070, -0.0092, 0.1985),
    1.50: (-1.0597, 0.2590, -0.2590, -0.0030, 0.1900),
    2.00: (-0.9880, 0.2043, -0.2043, 0.0013, 0.1611),
    2.50: (-0.9420, 0.1657, -0.1657, 0.0027, 0.1280),
    3.00: (-0.9170, 0.1380, -0.1380, 0.0030, 0.0997),
}


def make_hamiltonian(coefficients: tuple[float, float, float, float, float]) -> SparsePauliOp:
    return SparsePauliOp.from_list(
        [
            ("II", coefficients[0]),
            ("IZ", coefficients[1]),
            ("ZI", coefficients[2]),
            ("ZZ", coefficients[3]),
            ("XX", coefficients[4]),
        ]
    )


def build_vqe_circuit(params: np.ndarray) -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.ry(params[0], 0)
    qc.ry(params[1], 1)
    qc.cx(0, 1)
    qc.ry(params[2], 0)
    qc.ry(params[3], 1)
    return qc


def expectation_value(params: np.ndarray, hamiltonian: SparsePauliOp) -> float:
    state = Statevector.from_instruction(build_vqe_circuit(params))
    return float(np.real(state.expectation_value(hamiltonian)))


def exact_ground_energy(hamiltonian: SparsePauliOp) -> float:
    eigenvalues = np.linalg.eigvalsh(hamiltonian.to_matrix())
    return float(np.min(np.real(eigenvalues)))


def optimize_vqe(
    hamiltonian: SparsePauliOp,
    initial_params: np.ndarray,
    maxiter: int = 200,
) -> tuple[object, list[float]]:
    history: list[float] = []

    def objective(params: np.ndarray) -> float:
        value = expectation_value(params, hamiltonian)
        history.append(value)
        return value

    result = minimize(
        objective,
        initial_params,
        method="COBYLA",
        options={"maxiter": maxiter, "tol": 1e-6},
    )
    return result, history


def save_line_plot(values: list[float], reference: float, path: Path) -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(values, color="#0f4c81", linewidth=1.8, label="VQE energy")
    plt.axhline(reference, color="#c0392b", linestyle="--", linewidth=1.5, label="Exact ground energy")
    plt.xlabel("Iteration")
    plt.ylabel("Energy (Hartree)")
    plt.title("VQE Convergence for H2 at 0.735 A")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def save_probability_plot(probabilities: dict[str, float], path: Path) -> None:
    states = list(probabilities.keys())
    values = list(probabilities.values())
    plt.figure(figsize=(6, 4))
    plt.bar(states, values, color=["#0f4c81", "#3c8dbc", "#8fbcd4", "#cfe3ef"])
    plt.ylim(0, 1)
    plt.xlabel("Computational basis state")
    plt.ylabel("Probability")
    plt.title("Optimized state probability distribution")
    for index, value in enumerate(values):
        plt.text(index, value + 0.02, f"{value:.3f}", ha="center")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def save_pes_plot(distances: list[float], exact_values: list[float], vqe_values: list[float], path: Path) -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(distances, exact_values, "o-", color="#117a65", linewidth=2, label="Exact")
    plt.plot(distances, vqe_values, "s--", color="#d68910", linewidth=2, label="VQE")
    plt.xlabel("Bond distance (Angstrom)")
    plt.ylabel("Ground-state energy (Hartree)")
    plt.title("H2 Potential Energy Surface")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def main() -> None:
    np.random.seed(42)

    equilibrium_hamiltonian = make_hamiltonian(H2_COEFFICIENTS[EQUILIBRIUM_DISTANCE])
    exact_energy = exact_ground_energy(equilibrium_hamiltonian)
    initial_params = np.random.uniform(0, 2 * np.pi, size=4)
    optimization_result, energy_history = optimize_vqe(equilibrium_hamiltonian, initial_params)

    optimized_params = optimization_result.x
    optimized_circuit = build_vqe_circuit(optimized_params)
    optimized_state = Statevector.from_instruction(optimized_circuit)
    basis_probabilities = {
        state: float(probability)
        for state, probability in optimized_state.probabilities_dict().items()
    }

    distances: list[float] = []
    exact_curve: list[float] = []
    vqe_curve: list[float] = []
    warm_start = optimized_params.copy()

    for distance, coefficients in H2_COEFFICIENTS.items():
        hamiltonian = make_hamiltonian(coefficients)
        exact_value = exact_ground_energy(hamiltonian)
        result, _ = optimize_vqe(hamiltonian, warm_start, maxiter=150)
        warm_start = result.x

        distances.append(distance)
        exact_curve.append(exact_value)
        vqe_curve.append(float(result.fun))

    save_line_plot(energy_history, exact_energy, FIGURES_DIR / "vqe_loss.png")
    save_probability_plot(basis_probabilities, FIGURES_DIR / "optimized_state_probabilities.png")
    save_pes_plot(distances, exact_curve, vqe_curve, FIGURES_DIR / "h2_potential_energy_surface.png")

    circuit_diagram = optimized_circuit.draw(output="text")
    (ROOT / "vqe_circuit_diagram.txt").write_text(str(circuit_diagram), encoding="utf-8")

    print("ASSIGNMENT 2 RESULTS")
    print("=" * 60)
    print(f"Equilibrium bond distance: {EQUILIBRIUM_DISTANCE:.3f} Angstrom")
    print(f"Exact ground-state energy: {exact_energy:.6f} Hartree")
    print(f"VQE ground-state energy:   {optimization_result.fun:.6f} Hartree")
    print(f"Absolute error:            {abs(optimization_result.fun - exact_energy):.8f} Hartree")
    print(f"Optimizer evaluations:     {optimization_result.nfev}")
    print(f"Optimized parameters:      {np.round(optimized_params, 6).tolist()}")
    print("\nOptimized-state probabilities:")
    for state, probability in sorted(basis_probabilities.items()):
        print(f"  P({state}) = {probability:.6f}")

    min_index = int(np.argmin(vqe_curve))
    print("\nPotential-energy surface summary:")
    print(f"  Lowest VQE energy: {vqe_curve[min_index]:.6f} Hartree at {distances[min_index]:.3f} Angstrom")
    print(f"  Lowest exact energy: {min(exact_curve):.6f} Hartree at {distances[int(np.argmin(exact_curve))]:.3f} Angstrom")
    print(f"  Max PES absolute error: {max(abs(a - b) for a, b in zip(exact_curve, vqe_curve)):.8f} Hartree")
    print("\nGenerated files:")
    print(f"  {FIGURES_DIR / 'vqe_loss.png'}")
    print(f"  {FIGURES_DIR / 'optimized_state_probabilities.png'}")
    print(f"  {FIGURES_DIR / 'h2_potential_energy_surface.png'}")
    print(f"  {ROOT / 'vqe_circuit_diagram.txt'}")


if __name__ == "__main__":
    main()