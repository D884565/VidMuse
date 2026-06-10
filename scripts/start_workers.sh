#!/bin/bash
# 多队列Celery Worker启动脚本

echo "Starting VidMuse task workers..."

# 检查是否在项目根目录
if [ ! -d "backend" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# 激活虚拟环境（如果有）
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 创建日志目录
mkdir -p logs

# 启动视频生产队列Worker
echo "Starting video production worker (concurrency: 2)..."
celery -A backend.v1.app.generate.tasks.celery_app worker -Q video_production --concurrency=2 -n video_prod_worker@%h --loglevel=info --detach --logfile=logs/video_production_worker.log

# 启动爆款解析队列Worker
echo "Starting video analysis worker (concurrency: 1)..."
celery -A backend.v1.app.generate.tasks.celery_app worker -Q video_analysis --concurrency=1 -n video_analysis_worker@%h --loglevel=info --detach --logfile=logs/video_analysis_worker.log

# 启动定时聚类队列Worker
echo "Starting scheduled clustering worker (concurrency: 1)..."
celery -A backend.v1.app.generate.tasks.celery_app worker -Q scheduled_clustering --concurrency=1 -n clustering_worker@%h --loglevel=info --detach --logfile=logs/clustering_worker.log

# 启动默认队列Worker
echo "Starting default worker (concurrency: 3)..."
celery -A backend.v1.app.generate.tasks.celery_app worker -Q default --concurrency=3 -n default_worker@%h --loglevel=info --detach --logfile=logs/default_worker.log

# 启动定时任务调度器（Beat）
echo "Starting Celery Beat scheduler..."
celery -A backend.v1.app.generate.tasks.celery_app beat --loglevel=info --detach --logfile=logs/celery_beat.log

echo "All workers started successfully!"
echo "Log files are stored in logs/ directory"
echo "To stop all workers: pkill -f 'celery.*worker'"
echo "To stop Beat: pkill -f 'celery.*beat'"
