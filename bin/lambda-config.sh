#!/bin/bash
# Lambda Configuration Management Script
# Manages ephemeral storage and other Lambda function configurations

set -e

# Default configuration
DEFAULT_MEMORY=2048
DEFAULT_TIMEOUT=900
DEFAULT_STORAGE=1024
DEFAULT_REGION="us-west-2"

show_usage() {
    echo "Lambda Configuration Management"
    echo "==============================="
    echo ""
    echo "Usage: $0 <command> <function-name> [options]"
    echo ""
    echo "Commands:"
    echo "  show <function>              Show current configuration"
    echo "  update-storage <function>    Update ephemeral storage size"
    echo "  update-memory <function>     Update memory allocation"
    echo "  update-timeout <function>    Update timeout"
    echo "  optimize-ml <function>       Apply ML-optimized settings (2048MB, 1024MB storage, 15min)"
    echo ""
    echo "Options:"
    echo "  --memory SIZE                Memory in MB (default: ${DEFAULT_MEMORY})"
    echo "  --timeout SECONDS            Timeout in seconds (default: ${DEFAULT_TIMEOUT})"
    echo "  --storage SIZE               Ephemeral storage in MB (default: ${DEFAULT_STORAGE})"
    echo "  --region REGION              AWS region (default: ${DEFAULT_REGION})"
    echo ""
    echo "Examples:"
    echo "  $0 show RunNewvelles-qa"
    echo "  $0 update-storage RunNewvelles-qa --storage 1024"
    echo "  $0 optimize-ml RunNewvelles-qa"
    echo "  $0 update-memory RunNewvelles-qa --memory 3008"
}

show_config() {
    local function_name=$1
    local region=${2:-$DEFAULT_REGION}
    
    echo "📊 Current configuration for: ${function_name}"
    echo "=============================================="
    
    aws lambda get-function-configuration \
        --function-name "${function_name}" \
        --region "${region}" \
        --query '{
            Runtime: Runtime,
            MemorySize: MemorySize,
            Timeout: Timeout,
            EphemeralStorage: EphemeralStorage.Size,
            Architecture: Architectures[0],
            LastModified: LastModified,
            CodeSize: CodeSize,
            Environment: Environment.Variables
        }' \
        --output table
}

update_storage() {
    local function_name=$1
    local storage_size=$2
    local region=${3:-$DEFAULT_REGION}
    
    echo "💾 Updating ephemeral storage for: ${function_name}"
    echo "New storage size: ${storage_size}MB"
    echo ""
    
    aws lambda update-function-configuration \
        --function-name "${function_name}" \
        --ephemeral-storage Size=${storage_size} \
        --region "${region}"
    
    if [ $? -eq 0 ]; then
        echo "✅ Ephemeral storage updated successfully"
    else
        echo "❌ Failed to update ephemeral storage"
        exit 1
    fi
}

update_memory() {
    local function_name=$1
    local memory_size=$2
    local region=${3:-$DEFAULT_REGION}
    
    echo "🧠 Updating memory for: ${function_name}"
    echo "New memory size: ${memory_size}MB"
    echo ""
    
    aws lambda update-function-configuration \
        --function-name "${function_name}" \
        --memory-size ${memory_size} \
        --region "${region}"
    
    if [ $? -eq 0 ]; then
        echo "✅ Memory updated successfully"
    else
        echo "❌ Failed to update memory"
        exit 1
    fi
}

update_timeout() {
    local function_name=$1
    local timeout_seconds=$2
    local region=${3:-$DEFAULT_REGION}
    
    echo "⏱️ Updating timeout for: ${function_name}"
    echo "New timeout: ${timeout_seconds} seconds"
    echo ""
    
    aws lambda update-function-configuration \
        --function-name "${function_name}" \
        --timeout ${timeout_seconds} \
        --region "${region}"
    
    if [ $? -eq 0 ]; then
        echo "✅ Timeout updated successfully"
    else
        echo "❌ Failed to update timeout"
        exit 1
    fi
}

optimize_ml() {
    local function_name=$1
    local region=${2:-$DEFAULT_REGION}
    
    echo "🤖 Applying ML-optimized configuration to: ${function_name}"
    echo "========================================================="
    echo ""
    echo "ML-Optimized Settings:"
    echo "  • Memory: ${DEFAULT_MEMORY}MB (for TensorFlow)"
    echo "  • Ephemeral Storage: ${DEFAULT_STORAGE}MB (for 504MB model)"
    echo "  • Timeout: ${DEFAULT_TIMEOUT}s (15 minutes for ML processing)"
    echo ""
    
    # Update all settings in one call
    aws lambda update-function-configuration \
        --function-name "${function_name}" \
        --memory-size ${DEFAULT_MEMORY} \
        --timeout ${DEFAULT_TIMEOUT} \
        --ephemeral-storage Size=${DEFAULT_STORAGE} \
        --region "${region}"
    
    if [ $? -eq 0 ]; then
        echo "✅ ML optimization complete"
        echo ""
        echo "📊 Updated configuration:"
        show_config "${function_name}" "${region}"
    else
        echo "❌ Failed to apply ML optimization"
        exit 1
    fi
}

# Parse command line arguments
COMMAND=$1
FUNCTION_NAME=$2
shift 2

# Parse options
MEMORY=$DEFAULT_MEMORY
TIMEOUT=$DEFAULT_TIMEOUT
STORAGE=$DEFAULT_STORAGE
REGION=$DEFAULT_REGION

while [[ $# -gt 0 ]]; do
    case $1 in
        --memory)
            MEMORY="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --storage)
            STORAGE="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$COMMAND" ] || [ -z "$FUNCTION_NAME" ]; then
    show_usage
    exit 1
fi

# Execute command
case $COMMAND in
    show)
        show_config "$FUNCTION_NAME" "$REGION"
        ;;
    update-storage)
        update_storage "$FUNCTION_NAME" "$STORAGE" "$REGION"
        ;;
    update-memory)
        update_memory "$FUNCTION_NAME" "$MEMORY" "$REGION"
        ;;
    update-timeout)
        update_timeout "$FUNCTION_NAME" "$TIMEOUT" "$REGION"
        ;;
    optimize-ml)
        optimize_ml "$FUNCTION_NAME" "$REGION"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
