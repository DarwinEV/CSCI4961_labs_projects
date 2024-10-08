import gym
from gym import spaces
import hashlib
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import Aer
from qiskit.circuit.library import HGate, CXGate, SGate, TGate, XGate, YGate, ZGate
from qiskit.quantum_info import Operator

# Define target unitary matrices
H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)  # Hadamard gate

CNOT = np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 0]
])  # CNOT gate

bell_state_unitary = Operator(CNOT) @ Operator(np.kron(H, np.eye(2)))  # Bell state unitary

cz_matrix = np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, -1]
])  # CZ gate

swap_matrix = np.array([
    [1, 0, 0, 0],
    [0, 0, 1, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1]
])  # SWAP gate

iswap_matrix = np.array([
    [1, 0, 0, 0],
    [0, 0, 1j, 0],
    [0, 1j, 0, 0],
    [0, 0, 0, 1]
])  # iSWAP gate

class QuantumEnv(gym.Env):
    def __init__(self):
        super(QuantumEnv, self).__init__()

        # Initialize environment with 2 qubits
        self.num_qubits = 2
        self.circuit = QuantumCircuit(self.num_qubits)
        self.target_unitary = iswap_matrix # Target unitary matrix

        # Define action and observation space
        self.action_space = spaces.Discrete(14)  # 14 possible actions (quantum gates)
        self.observation_space = spaces.Discrete(100)  # Number of possible states (hashes)

        # Maps to track states and their indices
        self.state_to_index = {}
        self.index_to_state = []

    def reset(self):
        # Reset the circuit and return the state index
        self.circuit = QuantumCircuit(self.num_qubits)
        return self.get_state_index(self.circuit)

    def step(self, action, qubits):
        # Apply action to the circuit and return the new state index, reward, and done flag
        self.circuit.append(action, qubits)
        state_index = self.get_state_index(self.circuit)
        reward, done = self._reward(self.target_unitary)
        return state_index, reward, done

    def render(self):
        # Print the current circuit
        print(self.circuit.draw())

    def _hash_circuit(self, circuit: QuantumCircuit) -> str:
        # Generate a hash for the circuit
        circuit_str = circuit.draw(output='text').__str__()
        circuit_hash = hashlib.sha256(circuit_str.encode('utf-8')).hexdigest()
        hash_int = int(circuit_hash, 16)
        return hash_int % 100

    def get_state_index(self, state: QuantumCircuit) -> int:
        # Get or create an index for the given circuit state
        state_hash = self._hash_circuit(state)
        if state_hash not in self.state_to_index:
            index = len(self.state_to_index)
            self.state_to_index[state_hash] = index
            self.index_to_state.append(state_hash)
        return self.state_to_index[state_hash]

    def get_state_from_index(self, index: int) -> QuantumCircuit:
        # Get the circuit corresponding to a given state index
        state_hash = self.index_to_state[index]
        for circuit_hash, idx in self.state_to_index.items():
            if idx == index:
                return self._hash_circuit(circuit_hash)
        return None

    def _reward(self, target_unitary):
        # Calculate reward based on the fidelity of the circuit's unitary matrix to the target unitary
        simulator = Aer.get_backend('unitary_simulator')
        result = simulator.run(transpile(self.circuit, simulator)).result()
        unitary = result.get_unitary(self.circuit)

        unitary_array = np.asarray(unitary)
        target_unitary_array = np.asarray(target_unitary)

        # Compute fidelity
        fidelity = np.abs(np.trace(unitary_array.conj().T @ target_unitary_array)) / (2 ** self.num_qubits)

        # Reward based on fidelity and circuit size
        reward = -5 * self.circuit.size()
        done = False
        if fidelity > 0.99:
            done = True
            reward += 100
        return reward, done

    def close(self):
        # Close any resources if needed
        pass

# Define the Q-learning agent
class QLearningAgent:
    def __init__(self, state_size, action_size, alpha, gamma, epsilon, decay_rate, epsilon_min):
        # Initialize the Q-learning agent
        self.state_size = state_size
        self.action_size = action_size
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.decay_rate = decay_rate
        self.epsilon_min = epsilon_min
        # Initialize the Q-table with zeros
        self.q_table = np.zeros((state_size, action_size))
    
    def choose_action(self, state_index):
        # Choose an action based on exploration or exploitation
        if np.random.rand() < self.epsilon:
            action = np.random.randint(self.action_size)  # Random action (exploration)
        else:
            action = np.argmax(self.q_table[state_index])  # Best action (exploitation)
        
        possible_actions = [
            [HGate(), [0]],
            [HGate(), [1]],
            [CXGate(), [0, 1]],
            [CXGate(), [1, 0]],
            [SGate(), [0]],
            [SGate(), [1]],
            [TGate(), [0]],
            [TGate(), [1]],
            [XGate(), [0]],
            [XGate(), [1]],
            [YGate(), [0]],
            [YGate(), [1]],
            [ZGate(), [0]],
            [ZGate(), [1]],
        ]
        
        return possible_actions[action], action
    
    def update_q_table(self, state_index, action, reward, next_state_index):
        # Update the Q-table based on the agent's experience
        self.q_table[state_index, action] += self.alpha * (
            reward + self.gamma * np.max(self.q_table[next_state_index]) - self.q_table[state_index, action]
        )
    
    def decay_exploration(self):
        # Decay the exploration rate
        self.epsilon = max(self.epsilon_min, self.epsilon * self.decay_rate)

# Train the agent
def train_agent(agent, environment, episodes, max_steps_per_episode):
    for episode in range(episodes):
        # Reset the environment at the beginning of each episode
        state_index = environment.reset()
        episode_reward = 0
        for step in range(max_steps_per_episode):
            # Choose an action
            action, action_index = agent.choose_action(state_index)
            
            # Take the action and observe the outcome
            next_state_index, reward, done = environment.step(action[0], action[1])
            episode_reward += reward 
            # Update the Q-table
            agent.update_q_table(state_index, action_index, reward, next_state_index)
            
            # Update the state
            state_index = next_state_index
            
            # Check if the episode is done
            if done:
                print("Generated circuit:")
                environment.render()
                print(f"Episode {episode + 1}: Total Reward = {episode_reward}")
                break
            if environment.circuit.size() > 10:
                episode_reward -= 100  # Negative reward for exceeding maximum gates
                break
        
        # Save results every 100 episodes
        if (episode + 1) % 100 == 0:
            print(f"Episode {episode + 1}: Total Reward = {episode_reward}")
        agent.decay_exploration()

# Test the agent
def test_agent(agent, environment, episodes, max_steps_per_episode):
    for episode in range(episodes):
        # Reset the environment
        environment.reset()
        state_index = environment.reset()

        for step in range(max_steps_per_episode):
            # Choose an action (exploitation only, no exploration)
            action = agent.choose_action(state_index)
            
            # Take the action and observe the outcome
            next_state_index, reward, done = environment.step(action)
            
            # Update the state
            state_index = next_state_index
            
            # Render the environment (optional)
            environment.render()
            
            # Check if the episode is done
            if done:
                break

# Main function
if __name__ == "__main__":
    # Initialize environment and agent
    environment = QuantumEnv()
    agent = QLearningAgent(state_size=100, action_size=14, alpha=0.05, gamma=0.95, epsilon=0.9, decay_rate=0.99, epsilon_min=0.01)

    # Train the agent
    train_agent(agent, environment, episodes=100000, max_steps_per_episode=10000)
    
    # Test the agent
    test_agent(agent, environment, episodes=100000, max_steps_per_episode=10000)
