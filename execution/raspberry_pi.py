"""
Raspberry Pi Integration for BrachioGraph Hardware
Handles job export, SCP transfer, and SSH execution
"""
import json
import subprocess
import os
from typing import List, Tuple, Dict, Any
from config import (
    RASPBERRY_PI_HOST, 
    RASPBERRY_PI_USER, 
    RASPBERRY_PI_RUNJOB_PATH,
    RASPBERRY_PI_JOB_PATH,
    DRAWING_BOX
)
from utils.logger import get_logger

logger = get_logger(__name__)


class RaspberryPiDriver:
    """
    Driver for executing drawing jobs on Raspberry Pi via SSH/SCP.
    """
    
    def __init__(self, host: str = None, user: str = None):
        """
        Initialize Pi driver.
        
        Args:
            host: Pi hostname or IP (default from config)
            user: Pi username (default from config)
        """
        self.host = host or RASPBERRY_PI_HOST
        self.user = user or RASPBERRY_PI_USER
        self.job_file = "job.json"  # Local job file
        
        logger.info(f"RaspberryPi driver initialized for {self.user}@{self.host}")
    
    def export_job(self, 
                   strokes: List[List[Tuple[float, float]]],
                   use_normalized: bool = True,
                   metadata: Dict[str, Any] = None) -> str:
        """
        Export strokes to job JSON file.
        
        Args:
            strokes: List of polylines (normalized [0,1] coordinates)
            use_normalized: If True, use Format B with normalized coords
            metadata: Optional metadata to include
        
        Returns:
            Path to generated job file
        """
        # Convert strokes to list of lists of [x, y]
        lines = [[[float(x), float(y)] for x, y in stroke] for stroke in strokes]
        
        if use_normalized:
            # Format B: Structured with normalized coordinates
            # Convert mm bounds to cm for BrachioGraph
            bounds_cm = {
                "min_x": DRAWING_BOX["min_x"] / 10.0,
                "max_x": DRAWING_BOX["max_x"] / 10.0,
                "min_y": DRAWING_BOX["min_y"] / 10.0,
                "max_y": DRAWING_BOX["max_y"] / 10.0
            }
            
            job_data = {
                "format": "plot_job_v1",
                "coords": "normalized",
                "bounds_cm": bounds_cm,
                "lines": lines
            }
            
            if metadata:
                job_data["metadata"] = metadata
        else:
            # Format A: Simple array (assumes coords are already in cm)
            job_data = lines
        
        # Write to file
        with open(self.job_file, 'w') as f:
            json.dump(job_data, f, indent=2)
        
        logger.info(f"Exported {len(lines)} polylines to {self.job_file}")
        return self.job_file
    
    def send_job(self, local_path: str = None) -> bool:
        """
        Send job file to Raspberry Pi via SCP.
        
        Args:
            local_path: Local job file path (default: self.job_file)
        
        Returns:
            True if successful
        """
        local_path = local_path or self.job_file
        
        if not os.path.exists(local_path):
            logger.error(f"Job file not found: {local_path}")
            return False
        
        # SCP command
        remote_path = f"{self.user}@{self.host}:{RASPBERRY_PI_JOB_PATH}"
        cmd = ["scp", local_path, remote_path]
        
        logger.info(f"Sending job to Pi: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"✓ Job sent to Pi: {RASPBERRY_PI_JOB_PATH}")
                return True
            else:
                logger.error(f"SCP failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("SCP timeout - check Pi connection")
            return False
        except FileNotFoundError:
            logger.error("scp command not found - ensure OpenSSH is installed")
            return False
        except Exception as e:
            logger.error(f"SCP error: {e}")
            return False
    
    def execute_job(self, dry_run: bool = False) -> bool:
        """
        Execute job on Raspberry Pi via SSH.
        
        Args:
            dry_run: If True, run with --dry-run flag (no hardware movement)
        
        Returns:
            True if successful
        """
        # Build SSH command
        dry_run_flag = " --dry-run" if dry_run else ""
        remote_cmd = f"python3 {RASPBERRY_PI_RUNJOB_PATH} {RASPBERRY_PI_JOB_PATH}{dry_run_flag}"
        
        ssh_cmd = ["ssh", f"{self.user}@{self.host}", remote_cmd]
        
        logger.info(f"Executing job on Pi: {remote_cmd}")
        
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for drawing
            )
            
            # Log output
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    logger.info(f"[Pi] {line}")
            
            if result.returncode == 0:
                logger.info("✓ Drawing complete on Pi")
                return True
            else:
                logger.error(f"Drawing failed on Pi:")
                if result.stderr:
                    for line in result.stderr.strip().split('\n'):
                        logger.error(f"[Pi] {line}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("SSH timeout - drawing took too long or Pi not responding")
            return False
        except FileNotFoundError:
            logger.error("ssh command not found - ensure OpenSSH is installed")
            return False
        except Exception as e:
            logger.error(f"SSH error: {e}")
            return False
    
    def send_and_execute(self, 
                        strokes: List[List[Tuple[float, float]]],
                        metadata: Dict[str, Any] = None,
                        dry_run: bool = False) -> bool:
        """
        Complete workflow: Export → Send → Execute
        
        Args:
            strokes: List of polylines (normalized coordinates)
            metadata: Optional metadata
            dry_run: If True, test without moving hardware
        
        Returns:
            True if successful
        """
        logger.info(f"Starting Pi execution workflow ({len(strokes)} strokes)")
        
        # 1. Export job
        job_file = self.export_job(strokes, use_normalized=True, metadata=metadata)
        
        # 2. Send to Pi
        if not self.send_job(job_file):
            return False
        
        # 3. Execute on Pi
        if not self.execute_job(dry_run=dry_run):
            return False
        
        logger.info("✓ Complete workflow finished successfully")
        return True
    
    def test_connection(self) -> bool:
        """
        Test SSH connection to Raspberry Pi.
        
        Returns:
            True if connection successful
        """
        cmd = ["ssh", f"{self.user}@{self.host}", "echo 'Connection OK'"]
        
        logger.info(f"Testing connection to {self.host}...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and "Connection OK" in result.stdout:
                logger.info("✓ Connection to Pi successful")
                return True
            else:
                logger.error(f"Connection test failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Connection timeout - check Pi is on and accessible")
            return False
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False
    
    def check_runjob_installed(self) -> bool:
        """
        Check if runjob.py is installed on the Pi.
        
        Returns:
            True if runjob.py exists
        """
        cmd = ["ssh", f"{self.user}@{self.host}", f"test -f {RASPBERRY_PI_RUNJOB_PATH} && echo 'OK'"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0 and "OK" in result.stdout
        except:
            return False
    
    def install_runjob(self, local_runjob_path: str = "runjob.py") -> bool:
        """
        Install runjob.py on the Raspberry Pi.
        
        Args:
            local_runjob_path: Path to local runjob.py file
        
        Returns:
            True if successful
        """
        if not os.path.exists(local_runjob_path):
            logger.error(f"runjob.py not found at: {local_runjob_path}")
            return False
        
        # Send runjob.py to Pi
        remote_path = f"{self.user}@{self.host}:{RASPBERRY_PI_RUNJOB_PATH}"
        cmd = ["scp", local_runjob_path, remote_path]
        
        logger.info(f"Installing runjob.py on Pi...")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Make it executable
                chmod_cmd = ["ssh", f"{self.user}@{self.host}", f"chmod +x {RASPBERRY_PI_RUNJOB_PATH}"]
                subprocess.run(chmod_cmd, timeout=10)
                
                logger.info(f"✓ runjob.py installed at {RASPBERRY_PI_RUNJOB_PATH}")
                return True
            else:
                logger.error(f"Failed to install runjob.py: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Installation error: {e}")
            return False


def create_sample_jobs():
    """Create sample job files for testing."""
    
    # Sample 1: Format A (simple array, cm coordinates)
    sample_a = [
        [[1.0, 1.0], [8.0, 1.0], [8.0, 6.0], [1.0, 6.0], [1.0, 1.0]],  # Square
        [[2.5, 2.0], [3.5, 2.0], [3.5, 3.0], [2.5, 3.0], [2.5, 2.0]]   # Small square
    ]
    
    with open("sample_job_a.json", 'w') as f:
        json.dump(sample_a, f, indent=2)
    
    # Sample 2: Format B (structured, normalized coordinates)
    sample_b = {
        "format": "plot_job_v1",
        "coords": "normalized",
        "bounds_cm": {"min_x": 0.0, "max_x": 10.0, "min_y": 0.0, "max_y": 10.0},
        "lines": [
            [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9], [0.1, 0.1]],  # Square
            [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]]   # Inner square
        ],
        "metadata": {
            "prompt": "draw two squares",
            "timestamp": "2026-01-11T10:00:00Z"
        }
    }
    
    with open("sample_job_b.json", 'w') as f:
        json.dump(sample_b, f, indent=2)
    
    print("Created sample_job_a.json and sample_job_b.json")
