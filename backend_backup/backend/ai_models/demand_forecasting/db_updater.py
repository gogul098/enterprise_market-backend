import pymysql
from sshtunnel import SSHTunnelForwarder

def push_forecasts_to_db(forecast_df, pem_file_path="../LambdaFinancials.pem"):
    """
    Connects to the AWS MySQL database via SSH Tunnel and inserts the forecasted
    demand rows into the demand_forecasts table.
    """
    ssh_host = '13.201.224.132'
    ssh_user = 'ubuntu'
    
    sql_host = '127.0.0.1'
    sql_user = 'root' 
    sql_password = '' 
    db_name = 'rocks'
    
    try:
        with SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_pkey=pem_file_path,
            remote_bind_address=(sql_host, 3306)
        ) as tunnel:
            
            connection = pymysql.connect(
                host='127.0.0.1',
                user=sql_user,
                password=sql_password,
                database=db_name,
                port=tunnel.local_bind_port
            )
            
            with connection.cursor() as cursor:
                # Prepare the insertion query based on your schema
                sql = """
                INSERT INTO demand_forecasts 
                (product_id, warehouse_id, target_date, predicted_demand, confidence_lower_bound, confidence_upper_bound) 
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                # Convert DataFrame rows into tuples for execution
                data_tuples = [
                    (
                        row.product_id, 
                        row.warehouse_id, 
                        row.target_date, 
                        row.predicted_demand, 
                        row.confidence_lower_bound, 
                        row.confidence_upper_bound
                    ) 
                    for index, row in forecast_df.iterrows()
                ]
                
                # Use executemany for bulk insertion
                cursor.executemany(sql, data_tuples)
                
            connection.commit()
            connection.close()
            print(f"Successfully pushed {len(forecast_df)} forecast records to AWS database.")
            
    except Exception as e:
        print(f"Failed to push forecasts to AWS database: {e}")
