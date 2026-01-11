#!/usr/bin/env python3
"""
Test Raspberry Pi connection and setup
"""
import sys
from execution.raspberry_pi import RaspberryPiDriver, create_sample_jobs

def main():
    print("="*60)
    print("Raspberry Pi Connection Test")
    print("="*60)
    
    # Create Pi driver
    print("\n1. Initializing Pi driver...")
    pi = RaspberryPiDriver()
    print(f"   Target: {pi.user}@{pi.host}")
    
    # Test connection
    print("\n2. Testing SSH connection...")
    if not pi.test_connection():
        print("   ✗ Connection failed!")
        print("\n   Troubleshooting:")
        print("   - Check Pi is powered on")
        print("   - Verify network connection")
        print("   - Try: ssh pi@raspberrypi.local")
        print("   - Or use IP: ssh pi@<IP_ADDRESS>")
        return 1
    
    print("   ✓ Connection successful")
    
    # Check runjob.py
    print("\n3. Checking runjob.py installation...")
    if not pi.check_runjob_installed():
        print("   ! runjob.py not found on Pi")
        print("   Attempting to install...")
        if pi.install_runjob():
            print("   ✓ runjob.py installed")
        else:
            print("   ✗ Failed to install runjob.py")
            print("\n   Manual installation:")
            print(f"   scp runjob.py {pi.user}@{pi.host}:/home/pi/runjob.py")
            return 1
    else:
        print("   ✓ runjob.py already installed")
    
    # Generate sample jobs
    print("\n4. Generating sample job files...")
    create_sample_jobs()
    print("   ✓ Created sample_job_a.json and sample_job_b.json")
    
    # Test with sample job
    print("\n5. Testing with sample job (dry-run)...")
    
    # Create a simple test square
    test_strokes = [
        [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8], [0.2, 0.2]]
    ]
    
    # Export job
    job_file = pi.export_job(test_strokes, metadata={"test": "connection_test"})
    print(f"   ✓ Exported {job_file}")
    
    # Send to Pi
    if not pi.send_job(job_file):
        print("   ✗ Failed to send job")
        return 1
    print("   ✓ Sent to Pi")
    
    # Execute with dry-run
    if not pi.execute_job(dry_run=True):
        print("   ✗ Failed to execute (even in dry-run)")
        return 1
    print("   ✓ Dry-run successful")
    
    # Final summary
    print("\n" + "="*60)
    print("✓ All tests passed!")
    print("="*60)
    print("\nYour Raspberry Pi is ready to draw!")
    print("\nNext steps:")
    print("1. Set USE_RASPBERRY_PI=true in .env")
    print("2. Set SIMULATION_MODE=false in .env")
    print("3. Run your drawing app")
    print("\nOr test manually:")
    print(f"  ssh {pi.user}@{pi.host} \"python3 /home/pi/runjob.py /tmp/job.json\"")
    print("\n" + "="*60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
