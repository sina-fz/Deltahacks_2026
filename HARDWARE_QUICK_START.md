# Hardware Integration - Quick Start

## 🚀 Quick Setup (5 minutes)

### 1. Configure Your Laptop

Edit `.env`:
```bash
# Enable Pi mode
USE_RASPBERRY_PI=true
SIMULATION_MODE=false

# Pi connection
RASPBERRY_PI_HOST=raspberrypi.local
RASPBERRY_PI_USER=pi
```

### 2. Test Connection

```powershell
python test_pi_connection.py
```

This will:
- Test SSH connection
- Install `runjob.py` on Pi automatically
- Run a test drawing (dry-run)

### 3. Run Your App

```powershell
python run_webapp.py
```

**That's it!** Your drawings will now execute on the Raspberry Pi hardware.

---

## 📁 Files You Need

### On Raspberry Pi:
- `/home/pi/runjob.py` - Automatically installed by test script

### On Laptop:
- `execution/raspberry_pi.py` - Driver (already in project)
- `execution/plotter_driver.py` - Updated to use Pi (already updated)
- `config.py` - Pi settings (already added)

---

## 🔧 Manual Commands

### Send & Execute Job Manually

```powershell
# 1. Create job file locally
python -c "from execution.raspberry_pi import create_sample_jobs; create_sample_jobs()"

# 2. Send to Pi
scp sample_job_b.json pi@raspberrypi.local:/tmp/job.json

# 3. Execute on Pi
ssh pi@raspberrypi.local "python3 /home/pi/runjob.py /tmp/job.json"
```

### Test Without Moving Hardware

```powershell
ssh pi@raspberrypi.local "python3 /home/pi/runjob.py /tmp/job.json --dry-run"
```

---

## 📦 Sample Job Files

**Format A** (simple, cm coordinates):
```json
[
  [[1.0, 1.0], [8.0, 1.0], [8.0, 6.0], [1.0, 6.0], [1.0, 1.0]]
]
```

**Format B** (structured, normalized):
```json
{
  "format": "plot_job_v1",
  "coords": "normalized",
  "bounds_cm": {"min_x": 0, "max_x": 10, "min_y": 0, "max_y": 10},
  "lines": [[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9], [0.1, 0.1]]]
}
```

Your app automatically uses **Format B** (recommended).

---

## ⚙️ Configuration

### Drawing Bounds

Adjust in `config.py` to match your hardware:

```python
DRAWING_BOX = {
    "min_x": 0.0,     # mm
    "max_x": 200.0,   # mm (20cm)
    "min_y": 0.0,     # mm
    "max_y": 200.0    # mm (20cm)
}
```

### Arm Lengths

Edit `runjob.py` on Pi (lines 202-203):
```python
inner_arm=8,   # cm
outer_arm=8,   # cm
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't connect to Pi | Use IP: `RASPBERRY_PI_HOST=192.168.1.100` |
| Permission denied | Set up SSH key or use password |
| runjob.py not found | Run `python test_pi_connection.py` |
| Arm not moving | Check power, servos, and bounds |
| Drawing flipped | Adjust DRAWING_BOX orientation |

### Get Pi IP Address

```bash
# On Pi:
hostname -I

# Or from laptop:
ping raspberrypi.local
```

---

## 📊 Workflow

```
Drawing App (Laptop)
  └─ Generates strokes (normalized [0,1])
  └─ PlotterDriver detects Pi mode
      └─ RaspberryPiDriver.send_and_execute()
          ├─ 1. Export job.json (Format B)
          ├─ 2. SCP to Pi: /tmp/job.json
          └─ 3. SSH execute: runjob.py
              ├─ Parse JSON
              ├─ Map normalized → cm
              ├─ Initialize BrachioGraph
              └─ Execute drawing
```

---

## 🎯 Integration Points

Your app already integrates automatically! The code checks:

```python
# In plotter_driver.py
if USE_RASPBERRY_PI and not SIMULATION_MODE:
    # Use Pi via SSH/SCP
    pi_driver.send_and_execute(strokes)
else:
    # Use local simulation or hardware
    ...
```

No code changes needed - just set environment variables!

---

## 📖 Full Documentation

See `RASPBERRY_PI_SETUP.md` for:
- Detailed setup instructions
- Network configuration
- Advanced options
- Troubleshooting guide

---

## ✅ Checklist

- [ ] Pi powered on and connected
- [ ] SSH enabled on Pi
- [ ] Can ping/ssh to Pi from laptop
- [ ] `USE_RASPBERRY_PI=true` in `.env`
- [ ] `SIMULATION_MODE=false` in `.env`
- [ ] Ran `python test_pi_connection.py` successfully
- [ ] Adjusted DRAWING_BOX to match hardware
- [ ] Tested with `--dry-run` first
- [ ] Ready to draw! 🎨
