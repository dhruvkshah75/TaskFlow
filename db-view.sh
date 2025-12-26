#!/bin/bash
# Quick database viewer for TaskFlow

DB_CMD="kubectl exec -n taskflow deployment/postgres -- psql -U postgres -d taskflow_db"

case "${1:-help}" in
  tables)
    echo "📋 All Tables in Database:"
    $DB_CMD -c "\dt"
    ;;
    
  tasks)
    echo "📊 Tasks Overview:"
    $DB_CMD -c "SELECT status, COUNT(*) as count FROM tasks GROUP BY status ORDER BY status;"
    ;;
    
  recent)
    LIMIT=${2:-10}
    echo "🕐 Recent $LIMIT Tasks:"
    $DB_CMD -c "SELECT id, title, status, created_at FROM tasks ORDER BY created_at DESC LIMIT $LIMIT;"
    ;;
    
  users)
    echo "👥 All Users:"
    $DB_CMD -c "SELECT id, username, email, created_at FROM users ORDER BY created_at DESC;"
    ;;
    
  task)
    if [ -z "$2" ]; then
      echo "❌ Error: Please provide task ID"
      echo "Usage: $0 task <task_id>"
      exit 1
    fi
    echo "🔍 Task Details (ID: $2):"
    $DB_CMD -x -c "SELECT * FROM tasks WHERE id = $2;"
    ;;
    
  queued)
    LIMIT=${2:-20}
    echo "⏳ Queued Tasks (limit $LIMIT):"
    $DB_CMD -c "SELECT id, title, status, scheduled_at, created_at FROM tasks WHERE status = 'QUEUED' ORDER BY created_at DESC LIMIT $LIMIT;"
    ;;
    
  pending)
    LIMIT=${2:-20}
    echo "📝 Pending Tasks (limit $LIMIT):"
    $DB_CMD -c "SELECT id, title, status, scheduled_at, created_at FROM tasks WHERE status = 'PENDING' ORDER BY created_at DESC LIMIT $LIMIT;"
    ;;
    
  completed)
    LIMIT=${2:-20}
    echo "✅ Completed Tasks (limit $LIMIT):"
    $DB_CMD -c "SELECT id, title, status, created_at FROM tasks WHERE status = 'COMPLETED' ORDER BY created_at DESC LIMIT $LIMIT;"
    ;;
    
  structure)
    TABLE=${2:-tasks}
    echo "🏗️  Structure of table: $TABLE"
    $DB_CMD -c "\d $TABLE"
    ;;
    
  shell)
    echo "🐚 Entering PostgreSQL shell..."
    echo "Use \q to exit"
    kubectl exec -it -n taskflow deployment/postgres -- psql -U postgres -d taskflow_db
    ;;
    
  query)
    if [ -z "$2" ]; then
      echo "❌ Error: Please provide SQL query"
      echo "Usage: $0 query 'SELECT * FROM tasks LIMIT 5;'"
      exit 1
    fi
    echo "📊 Custom Query:"
    $DB_CMD -c "$2"
    ;;
    
  stats)
    echo "📈 Database Statistics:"
    echo ""
    echo "Total Tasks by Status:"
    $DB_CMD -c "SELECT status, COUNT(*) as count FROM tasks GROUP BY status ORDER BY status;"
    echo ""
    echo "Total Users:"
    $DB_CMD -c "SELECT COUNT(*) as user_count FROM users;"
    echo ""
    echo "Tasks Created Today:"
    $DB_CMD -c "SELECT COUNT(*) as today_count FROM tasks WHERE created_at >= CURRENT_DATE;"
    echo ""
    echo "Database Size:"
    $DB_CMD -c "SELECT pg_size_pretty(pg_database_size('taskflow_db')) as database_size;"
    ;;
    
  help|*)
    cat << 'HELP'
📚 TaskFlow Database Viewer - Usage Guide

Commands:
  tables              List all tables in database
  tasks               Show task count by status
  recent [N]          Show N recent tasks (default: 10)
  users               List all users
  task <id>           Show detailed info for specific task ID
  queued [N]          Show queued tasks (default: 20)
  pending [N]         Show pending tasks (default: 20)
  completed [N]       Show completed tasks (default: 20)
  structure [table]   Show table structure (default: tasks)
  shell               Open interactive PostgreSQL shell
  query 'SQL'         Run custom SQL query
  stats               Show database statistics
  help                Show this help message

Examples:
  ./db-view.sh tables
  ./db-view.sh recent 20
  ./db-view.sh task 1601
  ./db-view.sh query "SELECT * FROM users WHERE username LIKE 'stress%';"
  ./db-view.sh stats

HELP
    ;;
esac
