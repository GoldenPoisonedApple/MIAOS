import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Subset
import numpy as np
from sklearn.model_selection import train_test_split
from tqdm import tqdm
import os
import time  # 追加: 時間計測用

# --- Configuration (Optimized for RTX 5070) ---
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
BATCH_SIZE = 512 
LR = 0.001
LR_DECAY = 1e-07
TARGET_EPOCHS = 100
SHADOW_EPOCHS = 100
NUM_CLASSES = 100 

NUM_SHADOW_MODELS = 100
TARGET_TRAIN_SIZE = 15000 
NUM_WORKERS = 4 

print(f"Running on {DEVICE} ({torch.cuda.get_device_name(0)})")
print(f"Configuration: Batch={BATCH_SIZE}, Shadow Models={NUM_SHADOW_MODELS}, Workers={NUM_WORKERS}")

# --- Model Definitions ---
class TargetNet(nn.Module):
    def __init__(self):
        super(TargetNet, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.Tanh(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.Tanh(),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Linear(64 * 8 * 8, 128),
            nn.Tanh(),
            nn.Linear(128, NUM_CLASSES),
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x

class AttackNet(nn.Module):
    def __init__(self, input_dim):
        super(AttackNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 2)
        )

    def forward(self, x):
        return self.net(x)

def train_model(model, train_loader, epochs):
    model = model.to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LR, weight_decay=LR_DECAY)
    
    model.train()
    for _ in range(epochs):
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(DEVICE, non_blocking=True), labels.to(DEVICE, non_blocking=True)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
    return model

def get_predictions(model, loader):
    model.eval()
    preds = []
    labels_list = []
    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(DEVICE, non_blocking=True)
            outputs = torch.softmax(model(inputs), dim=1)
            preds.append(outputs.cpu())
            labels_list.append(labels)
    return torch.cat(preds), torch.cat(labels_list)

def get_accuracy(model, loader):
    correct = 0
    total = 0
    model.eval()
    with torch.no_grad():
        for inputs, labels in loader:
            inputs, labels = inputs.to(DEVICE, non_blocking=True), labels.to(DEVICE, non_blocking=True)
            outputs = model(inputs)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    return correct / total

def main():
    total_start_time = time.time()

    # --- 1. Data Preparation ---
    print("Preparing Data...")
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])
    
    full_train_set = torchvision.datasets.CIFAR100(root='./data', train=True, download=True, transform=transform)
    test_set = torchvision.datasets.CIFAR100(root='./data', train=False, download=True, transform=transform)
    
    indices = np.arange(len(full_train_set))
    target_train_indices, shadow_pool_indices = train_test_split(indices, train_size=TARGET_TRAIN_SIZE, random_state=42)
    
    target_train_loader = DataLoader(
        Subset(full_train_set, target_train_indices), 
        batch_size=BATCH_SIZE, shuffle=True, 
        num_workers=NUM_WORKERS, pin_memory=True
    )
    target_test_loader = DataLoader(
        test_set, batch_size=BATCH_SIZE, shuffle=False, 
        num_workers=NUM_WORKERS, pin_memory=True
    )

    # --- 2. Train Target Model ---
    print("\n[Phase 1] Training Target Model...")
    p1_start = time.time()
    
    target_model = TargetNet()
    target_model = train_model(target_model, target_train_loader, TARGET_EPOCHS)
    
    p1_end = time.time()
    p1_duration = p1_end - p1_start
    print(f">> Target Model Training Time: {p1_duration:.2f} sec")

    train_acc = get_accuracy(target_model, target_train_loader)
    test_acc = get_accuracy(target_model, target_test_loader)
    print(f"Target Result -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})")

    # --- 3. Train Shadow Models ---
    print(f"\n[Phase 2] Training {NUM_SHADOW_MODELS} Shadow Models...")
    p2_start = time.time()
    
    attack_x = []
    attack_y = [] 
    attack_classes = []
    
    for i in tqdm(range(NUM_SHADOW_MODELS), desc="Shadow Models"):
        sample_size = TARGET_TRAIN_SIZE
        
        shadow_train_idx = np.random.choice(shadow_pool_indices, sample_size, replace=False)
        shadow_train_subset = Subset(full_train_set, shadow_train_idx)
        
        shadow_train_loader = DataLoader(
            shadow_train_subset, batch_size=BATCH_SIZE, shuffle=True, 
            num_workers=NUM_WORKERS, pin_memory=True
        )
        
        remaining_indices = np.setdiff1d(shadow_pool_indices, shadow_train_idx)
        current_test_size = min(len(remaining_indices), sample_size)
        shadow_test_idx = np.random.choice(remaining_indices, current_test_size, replace=False)
        
        shadow_test_subset = Subset(full_train_set, shadow_test_idx)
        shadow_test_loader = DataLoader(
            shadow_test_subset, batch_size=BATCH_SIZE, shuffle=False, 
            num_workers=NUM_WORKERS, pin_memory=True
        )

        shadow_model = TargetNet()
        shadow_model = train_model(shadow_model, shadow_train_loader, SHADOW_EPOCHS)
        
        preds_in, labels_in = get_predictions(shadow_model, shadow_train_loader)
        for p, l in zip(preds_in, labels_in):
            attack_x.append(p.numpy())
            attack_y.append(1) 
            attack_classes.append(l.item())
            
        preds_out, labels_out = get_predictions(shadow_model, shadow_test_loader)
        for p, l in zip(preds_out, labels_out):
            attack_x.append(p.numpy())
            attack_y.append(0)
            attack_classes.append(l.item())

    p2_end = time.time()
    p2_duration = p2_end - p2_start
    avg_shadow_time = p2_duration / NUM_SHADOW_MODELS
    
    print(f">> Shadow Models Total Time: {p2_duration:.2f} sec")
    print(f">> Average Time per Shadow Model: {avg_shadow_time:.2f} sec")
    print(f">> Estimated Time for 100 Models: {(avg_shadow_time * 100) / 60:.2f} min")

    attack_x = torch.tensor(np.array(attack_x), dtype=torch.float32)
    attack_y = torch.tensor(np.array(attack_y), dtype=torch.long)
    attack_classes = np.array(attack_classes)

    # --- 4. Train Attack Models ---
    print("\n[Phase 3] Training Attack Models...")
    p3_start = time.time()
    
    attack_models = {}
    ATTACK_BATCH = 128
    
    for c in tqdm(range(NUM_CLASSES), desc="Attack Models"):
        idx = np.where(attack_classes == c)[0]
        if len(idx) == 0: continue
        
        c_x = attack_x[idx]
        c_y = attack_y[idx]
        
        dataset = torch.utils.data.TensorDataset(c_x, c_y)
        loader = DataLoader(dataset, batch_size=ATTACK_BATCH, shuffle=True)
        
        net = AttackNet(input_dim=NUM_CLASSES).to(DEVICE)
        optimizer = optim.Adam(net.parameters(), lr=0.01)
        criterion = nn.CrossEntropyLoss()
        
        net.train()
        for _ in range(50):
            for bx, by in loader:
                bx, by = bx.to(DEVICE), by.to(DEVICE)
                optimizer.zero_grad()
                out = net(bx)
                loss = criterion(out, by)
                loss.backward()
                optimizer.step()
        
        attack_models[c] = net

    p3_end = time.time()
    p3_duration = p3_end - p3_start
    print(f">> Attack Models Training Time: {p3_duration:.2f} sec")

    # --- 5. Evaluate ---
    print("\n[Phase 4] Evaluating...")
    t_preds_in, t_labels_in = get_predictions(target_model, target_train_loader)
    t_preds_out, t_labels_out = get_predictions(target_model, target_test_loader)
    
    correct = 0
    total = 0
    
    for p, l in zip(t_preds_in, t_labels_in):
        cls = l.item()
        if cls in attack_models:
            net = attack_models[cls]
            out = net(p.unsqueeze(0).to(DEVICE))
            if torch.argmax(out, dim=1).item() == 1: correct += 1
            total += 1
            
    for p, l in zip(t_preds_out, t_labels_out):
        cls = l.item()
        if cls in attack_models:
            net = attack_models[cls]
            out = net(p.unsqueeze(0).to(DEVICE))
            if torch.argmax(out, dim=1).item() == 0: correct += 1
            total += 1
            
    print(f"Final Attack Accuracy: {correct / total:.4f}")

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    print(f"\n=========================================")
    print(f"Total Execution Time: {total_duration:.2f} sec ({total_duration/60:.2f} min)")
    print(f"=========================================")

if __name__ == "__main__":
    main()