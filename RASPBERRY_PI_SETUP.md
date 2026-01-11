# Raspberry Pi Hardware Integration Setup

This guide explains how to set up and use the Raspberry Pi with your BrachioGraph drawing arm.

## Architecture

```
Laptop (Windows)           Raspberry Pi
┌───────────────┐         ┌──────────────┐
│               │         │              │
│  Drawing App  │ --SCP-> │  job.json    │
│  (Python)     │         │              │
│               │ --SSH-> │  runjob.py   │
│               │         │  (executes)  │
└───────────────┘         │              │
                          │ BrachioGraph │
                          │   Hardware   │
                          └──────────────┘
```

## Prerequisites

### On Raspberry Pi:
1. **Install Python 3 and BrachioGraph:**
   ```bash
   sudo apt-get update
   sudo apt-get install python3 python3-pip -y
   pip3 install brachiograph
   ```

2. **Enable SSH:**
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options → SSH → Enable
   ```

3. **Get Pi's IP address:**
   ```bash
   hostname -I
   # Note the first IP address (e.g., 192.168.1.100)
   ```

### On Laptop (Windows):
1. **Install OpenSSH Client** (if not already installed):
   - Settings → Apps → Optional Features
   - Add "OpenSSH Client"

2. **Set up SSH key** (recommended for passwordless access):
   ```powershell
   # Generate SSH key (if you don't have one)
   ssh-keygen -t rsa -b 4096
   
   # Copy key to Pi (replace with your Pi's IP)
   type $env:USERPROFILE\.ssh\id_rsa.pub | ssh pi@192.168.1.100 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
   ```

## Installation

### 1. Copy `runjob.py` to Raspberry Pi

**Option A: Automatic** (app will do this automatically on first run)

**Option B: Manual**
```powershell
# From your project directory
scp runjob.py pi@raspberrypi.local:/home/pi/runjob.py
ssh pi@raspberrypi.local "chmod +x /home/pi/runjob.py"
```

### 2. Configure Your Laptop

Edit `.env` file in your project root:

```bash
# Enable Raspberry Pi mode
USE_RASPBERRY_PI=true

# Pi connection (use IP if .local doesn't work)
RASPBERRY_PI_HOST=raspberrypi.local  # or 192.168.1.100
RASPBERRY_PI_USER=pi

# Turn off simulation
SIMULATION_MODE=false

# Drawing bounds (adjust to your hardware)
DRAWING_BOX_MIN_X=0.0
DRAWING_BOX_MAX_X=200.0
DRAWING_BOX_MIN_Y=0.0
DRAWING_BOX_MAX_Y=200.0
```

### 3. Test Connection

```python
from execution.raspberry_pi import RaspberryPiDriver

# Test connection
pi = RaspberryPiDriver()
if pi.test_connection():
    print("✓ Connected to Pi")
else:
    print("✗ Connection failed")
```

Or run the test script:
```powershell
python test_pi_connection.py
```

## Usage

### From Your App

The app automatically uses the Pi when `USE_RASPBERRY_PI=true`:

```python
from execution.plotter_driver import PlotterDriver
from execution.coordinate_mapper import CoordinateMapper

mapper = CoordinateMapper()
plotter = PlotterDriver(mapper)  # Automatically uses Pi

# Draw strokes (normalized [0,1] coordinates)
strokes = [
    [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9], [0.1, 0.1]]  # Square
]

plotter.execute_strokes(strokes)
```

### Manual Workflow

If you want to manually send jobs:

```python
from execution.raspberry_pi import RaspberryPiDriver

pi = RaspberryPiDriver()

# Define strokes
strokes = [
    [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9], [0.1, 0.1]]
]

# Export, send, and execute
pi.send_and_execute(strokes, metadata={"prompt": "draw a square"})
```

### Command Line (from laptop)

```powershell
# Test with sample job
python -c "from execution.raspberry_pi import create_sample_jobs; create_sample_jobs()"

# Send sample job
scp sample_job_b.json pi@raspberrypi.local:/tmp/job.json

# Execute with dry-run (no hardware movement)
ssh pi@raspberrypi.local "python3 /home/pi/runjob.py /tmp/job.json --dry-run"

# Execute for real
ssh pi@raspberrypi.local "python3 /home/pi/runjob.py /tmp/job.json"
```

### On Raspberry Pi Directly

```bash
# Test with dry-run
python3 runjob.py /tmp/job.json --dry-run

# Execute drawing
python3 runjob.py /tmp/job.json

# With custom bounds
python3 runjob.py /tmp/job.json --bounds-cm "0,15,0,15"

# Force coordinate mode
python3 runjob.py /tmp/job.json --coords normalized
```

## Job File Formats

### Format A: Simple Array (cm coordinates)
```json
[
  [[1.0, 1.0], [8.0, 1.0], [8.0, 6.0], [1.0, 6.0], [1.0, 1.0]],
  [[2.5, 2.0], [3.5, 2.0], [3.5, 3.0], [2.5, 3.0], [2.5, 2.0]]
]
```

### Format B: Structured (normalized or cm)
```json
{
  "format": "plot_job_v1",
  "coords": "normalized",
  "bounds_cm": {"min_x": 0, "max_x": 10, "min_y": 0, "max_y": 10},
  "lines": [
    [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9], [0.1, 0.1]]
  ],
  "metadata": {"prompt": "draw a square"}
}
```

## Troubleshooting

### Connection Issues

**Problem:** `ssh: Could not resolve hostname raspberrypi.local`
```powershell
# Use IP address instead
# Edit .env: RASPBERRY_PI_HOST=192.168.1.100
```

**Problem:** `Permission denied (publickey,password)`
```powershell
# Try with password first
ssh pi@raspberrypi.local
# Default password: raspberry

# Or set up SSH key (see Prerequisites)
```

**Problem:** `Connection timeout`
- Check Pi is powered on and connected to network
- Ping the Pi: `ping raspberrypi.local` or `ping 192.168.1.100`
- Check firewall settings on both laptop and Pi

### Drawing Issues

**Problem:** Arm not moving
```bash
# On Pi, check BrachioGraph installation
python3 -c "import brachiograph; print('OK')"

# Test with dry-run first
python3 runjob.py /tmp/job.json --dry-run
```

**Problem:** Coordinates out of bounds
```bash
# Check your hardware bounds
python3 -c "from brachiograph import BrachioGraph; bg = BrachioGraph(); print(bg.bounds)"

# Adjust bounds in .env or override in runjob.py
python3 runjob.py /tmp/job.json --bounds-cm "0,10,0,10"
```

**Problem:** Drawing is flipped or rotated
- Adjust DRAWING_BOX in config.py to match your hardware orientation
- BrachioGraph coordinate system: origin at bottom-left

### Performance

**Slow SSH/SCP:**
- Ensure Pi and laptop are on same network
- Use wired connection if possible
- Check network bandwidth

**Timeouts:**
- Increase timeout in raspberry_pi.py if drawing takes >5 minutes
- Or break drawing into smaller chunks

## Network Setup

### USB Ethernet Connection

If using USB-Ethernet adapter:

1. **On Pi:** Enable USB gadget mode (Raspberry Pi Zero/4 only)
   ```bash
   # Edit /boot/config.txt, add:
   dtoverlay=dwc2
   
   # Edit /boot/cmdline.txt, add after rootwait:
   modules-load=dwc2,g_ether
   ```

2. **On Laptop:** Share internet connection
   - Network settings → Ethernet → Properties
   - Enable "Allow other network users to connect"

3. **Connect and find IP:**
   ```powershell
   # Pi will appear as RNDIS device
   # Find IP with:
   arp -a | findstr "dynamic"
   ```

### Wi-Fi Connection

Configure Pi's Wi-Fi:
```bash
sudo raspi-config
# System Options → Wireless LAN → Enter SSID and password
```

## Hardware Configuration

Adjust in config.py or .env:

```python
# Drawing area (mm) - adjust to your hardware
DRAWING_BOX = {
    "min_x": 0.0,
    "max_x": 200.0,  # 20cm
    "min_y": 0.0,
    "max_y": 200.0   # 20cm
}
```

In runjob.py (lines 202-203), adjust arm lengths:
```python
inner_arm=8,   # Your inner arm length in cm
outer_arm=8,   # Your outer arm length in cm
```

## Development Tips

### Test Without Hardware

```python
# Export job only (doesn't send to Pi)
from execution.raspberry_pi import RaspberryPiDriver

pi = RaspberryPiDriver()
pi.export_job(strokes, metadata={"test": True})
# Creates job.json locally
```

### View Job on Pi

```bash
# SSH to Pi and cat the job
ssh pi@raspberrypi.local "cat /tmp/job.json"
```

### Monitor Drawing

```bash
# Watch Pi output in real-time
ssh pi@raspberrypi.local "python3 /home/pi/runjob.py /tmp/job.json" 2>&1 | tee drawing_log.txt
```

## Sample Jobs

Generate sample jobs:
```python
from execution.raspberry_pi import create_sample_jobs
create_sample_jobs()
# Creates: sample_job_a.json and sample_job_b.json
```

Test samples:
```powershell
scp sample_job_b.json pi@raspberrypi.local:/tmp/job.json
ssh pi@raspberrypi.local "python3 /home/pi/runjob.py /tmp/job.json --dry-run"
```

## Support

For issues:
1. Check logs on both laptop and Pi
2. Test with --dry-run first
3. Verify coordinates with sample jobs
4. Check hardware connections and power

**Useful Commands:**
```bash
# Pi logs
journalctl -xe | grep python

# Network connectivity
ping raspberrypi.local
ssh -v pi@raspberrypi.local  # verbose SSH

# BrachioGraph test
python3 -c "from brachiograph import BrachioGraph; bg = BrachioGraph(virtual=False); bg.park()"
```
