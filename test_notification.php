<?php

$url = "http://127.0.0.1:5000/api/send_notification";

$data = array(
    "title" => "PHP Test",
    "message" => "Notification from PHP"
);

$ch = curl_init($url);

curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

curl_setopt($ch, CURLOPT_HTTPHEADER, array(
    "Content-Type: application/json"
));

curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));

$response = curl_exec($ch);

if(curl_errno($ch)){
    echo "Curl Error: " . curl_error($ch);
}else{
    echo "Notification Sent Successfully";
    echo "<br>";
    echo $response;
}

curl_close($ch);

?>