try {
    $base='http://localhost'

    function GetToken {
        param($username,$password,$email,$role)
        $body = @{username=$username; password=$password; email=$email; role=$role} | ConvertTo-Json
        try {
            $reg = Invoke-RestMethod -Uri "$($base):8000/register" -Method POST -ContentType 'application/json' -Body $body -UseBasicParsing -ErrorAction Stop
            return 'Bearer ' + $reg.access_token
        } catch {
            Write-Host "Register failed for $username, trying login..."
            $loginBody = @{username=$username; password=$password} | ConvertTo-Json
            $login = Invoke-RestMethod -Uri "$($base):8000/login" -Method POST -ContentType 'application/json' -Body $loginBody -UseBasicParsing -ErrorAction Stop
            return 'Bearer ' + $login.access_token
        }
    }

    Write-Host '1) Get tokens for admin, doctor user and patient user'
    $adminToken = GetToken 'admin1' 'AdminPass1!' 'admin1@example.com' 'admin'
    Write-Host " admin token len: $($adminToken.Length)"
    $docToken = GetToken 'docuser' 'DocPass1!' 'docuser@example.com' 'doctor'
    Write-Host " doctor token len: $($docToken.Length)"
    $patToken = GetToken 'patuser' 'PatPass1!' 'patuser@example.com' 'patient'
    Write-Host " patient token len: $($patToken.Length)"

    Write-Host '2) Admin create doctor profile (if not exists)'
    $docProfile = @{first_name='Doc'; last_name='Tor'; specialization='General'; license_number=('LIC' + (Get-Random -Maximum 99999)); phone='111'; email='doc1@example.com'; consultation_fee=120.0; available_days='Mon,Tue,Wed'} | ConvertTo-Json
    $createDoc = Invoke-RestMethod -Uri "$($base):8002/doctors" -Method POST -ContentType 'application/json' -Body $docProfile -Headers @{Authorization=$adminToken} -UseBasicParsing -ErrorAction Stop
    $doctor_id = $createDoc.id
    Write-Host " doctor created id: $doctor_id"

    Write-Host '3) Patient create profile'
    $patProfile = @{first_name='Pat'; last_name='One'; date_of_birth='1990-01-01'; gender='female'; phone='123'; address='here'; blood_type='O+'; allergies='none'} | ConvertTo-Json
    try {
        $createPat = Invoke-RestMethod -Uri "$($base):8001/patients" -Method POST -ContentType 'application/json' -Body $patProfile -Headers @{Authorization=$patToken} -UseBasicParsing -ErrorAction Stop
        $patient_id = $createPat.id
        Write-Host " patient created id: $patient_id"
    } catch {
        Write-Host "Create patient returned error, trying to fetch existing profile..."
        $existing = Invoke-RestMethod -Uri "$($base):8001/patients/me" -Method GET -Headers @{Authorization=$patToken} -UseBasicParsing -ErrorAction Stop
        $patient_id = $existing.id
        Write-Host " existing patient id: $patient_id"
    }

    Write-Host '4) Patient create appointment'
    $apptBody = @{doctor_id=$doctor_id; appointment_date=(Get-Date -Format 'yyyy-MM-dd'); appointment_time='10:00'; reason='Checkup'} | ConvertTo-Json
    try {
        $createAppt = Invoke-RestMethod -Uri "$($base):8003/appointments" -Method POST -ContentType 'application/json' -Body $apptBody -Headers @{Authorization=$patToken} -UseBasicParsing -ErrorAction Stop
        $appointment_id = $createAppt.id
        Write-Host " appointment created id: $appointment_id"
    } catch {
        Write-Host "Create appointment failed, trying to find existing appointment..."
        $appts = Invoke-RestMethod -Uri "$($base):8003/appointments/my" -Method GET -Headers @{Authorization=$patToken} -UseBasicParsing -ErrorAction Stop
        $match = $appts | Where-Object { $_.appointment_date -eq (Get-Date -Format 'yyyy-MM-dd') -and $_.appointment_time -eq '10:00' }
        if ($match) { $appointment_id = $match[0].id; Write-Host " found appointment id: $appointment_id" } else { throw $_ }
    }

    Write-Host '5) Doctor create medical record'
    $recordBody = @{patient_id=$patient_id; appointment_id=$appointment_id; diagnosis='Healthy'; prescription='None'; lab_results='Normal'; notes='All good'; record_date=(Get-Date -Format 'yyyy-MM-dd')} | ConvertTo-Json
    $createRecord = Invoke-RestMethod -Uri "$($base):8004/records" -Method POST -ContentType 'application/json' -Body $recordBody -Headers @{Authorization=$docToken} -UseBasicParsing -ErrorAction Stop
    $record_id = $createRecord.id
    Write-Host " record created id: $record_id"

    Write-Host '6) Admin create invoice for appointment'
    $invoiceBody = @{patient_id=$patient_id; appointment_id=$appointment_id; amount=150.0; description='Consultation fee'; invoice_date=(Get-Date -Format 'yyyy-MM-dd'); due_date=((Get-Date).AddDays(30).ToString('yyyy-MM-dd')) } | ConvertTo-Json
    $createInvoice = Invoke-RestMethod -Uri "$($base):8006/invoices" -Method POST -ContentType 'application/json' -Body $invoiceBody -Headers @{Authorization=$adminToken} -UseBasicParsing -ErrorAction Stop
    $invoice_id = $createInvoice.id
    Write-Host " invoice created id: $invoice_id"

    Write-Host 'Scenario completed successfully.'
    Write-Host "Summary: doctor_id=$doctor_id, patient_id=$patient_id, appointment_id=$appointment_id, record_id=$record_id, invoice_id=$invoice_id"
} catch {
    Write-Host 'ERROR during scenario run:' $_.Exception.Message
    exit 1
} finally {
    exit 0
}
