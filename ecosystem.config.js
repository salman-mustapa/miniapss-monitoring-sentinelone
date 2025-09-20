module.exports = {
  apps: [
    {
      name: 'sentinelone-web',
      script: 'run.py',
      args: '--web',
      interpreter: 'python3',
      cwd: '/home/dcs_s4lm4n/Project/sentinelone_miniapps/miniapps-monitoring',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/dcs_s4lm4n/Project/sentinelone_miniapps/miniapps-monitoring'
      },
      log_file: '/dev/null',
      out_file: '/dev/null',
      error_file: '/dev/null',
      time: true
    },
    {
      name: 'sentinelone-polling',
      script: 'run.py',
      args: '--polling',
      interpreter: 'python3',
      cwd: '/home/dcs_s4lm4n/Project/sentinelone_miniapps/miniapps-monitoring',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/dcs_s4lm4n/Project/sentinelone_miniapps/miniapps-monitoring'
      },
      log_file: '/dev/null',
      out_file: '/dev/null',
      error_file: '/dev/null',
      time: true
    },
    {
      name: 'sentinelone-backup',
      script: 'run.py',
      args: '--backup',
      interpreter: 'python3',
      cwd: '/home/dcs_s4lm4n/Project/sentinelone_miniapps/miniapps-monitoring',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/dcs_s4lm4n/Project/sentinelone_miniapps/miniapps-monitoring'
      },
      log_file: '/dev/null',
      out_file: '/dev/null',
      error_file: '/dev/null',
      time: true,
      cron_restart: '0 2 * * *' // Restart daily at 2 AM
    }
  ],

  deploy: {
    production: {
      user: 'dcs_s4lm4n',
      host: 'localhost',
      ref: 'origin/main',
      repo: 'git@github.com:username/sentinelone-monitor.git',
      path: '/home/dcs_s4lm4n/Project/sentinelone_miniapps/miniapps-monitoring',
      'pre-deploy-local': '',
      'post-deploy': 'pip install -r requirements.txt && pm2 reload ecosystem.config.js --env production',
      'pre-setup': ''
    }
  }
};
